from threading import Lock
from typing import Any, Dict, List, Set

from app.agents.planner.plan_models import (
    AgentPlan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.agents.tools.tool_registry import (
    ToolDefinition,
    get_tool,
)


# ---------------------------------------------------------------------------
# MISSION CANCELLATION REGISTRY
# ---------------------------------------------------------------------------

MISSION_CANCELLATION_REGISTRY: Dict[str, bool] = {}

MISSION_CANCELLATION_LOCK = Lock()


def _normalize_mission_id(
    mission_id: str | None,
) -> str:
    return str(
        mission_id or ""
    ).strip()


def set_mission_cancelled(
    mission_id: str | None,
) -> bool:
    """
    Persist a backend cancellation request for a mission.

    Cancellation is cooperative: a currently executing tool is allowed
    to finish, and the executor prevents any remaining steps from starting.
    """

    normalized_id = _normalize_mission_id(
        mission_id
    )

    if not normalized_id:
        return False

    with MISSION_CANCELLATION_LOCK:
        MISSION_CANCELLATION_REGISTRY[
            normalized_id
        ] = True

    return True


def clear_mission_cancelled(
    mission_id: str | None,
) -> None:
    """
    Clear the cancellation state for a mission.
    """

    normalized_id = _normalize_mission_id(
        mission_id
    )

    if not normalized_id:
        return

    with MISSION_CANCELLATION_LOCK:
        MISSION_CANCELLATION_REGISTRY.pop(
            normalized_id,
            None,
        )


def is_mission_cancelled(
    mission_id: str | None,
) -> bool:
    """
    Check whether the mission has been explicitly cancelled.
    """

    normalized_id = _normalize_mission_id(
        mission_id
    )

    if not normalized_id:
        return False

    with MISSION_CANCELLATION_LOCK:
        return bool(
            MISSION_CANCELLATION_REGISTRY.get(
                normalized_id,
                False,
            )
        )


# ---------------------------------------------------------------------------
# EXECUTION RESULT
# ---------------------------------------------------------------------------

class ExecutionResult:
    """
    Result returned after an agent plan execution attempt.
    """

    def __init__(
        self,
        plan: AgentPlan,
        completed_steps: List[str],
        failed_steps: List[str],
        blocked_steps: List[str],
        context: Dict[str, Any] | None = None,
    ) -> None:
        self.plan = plan
        self.completed_steps = completed_steps
        self.failed_steps = failed_steps
        self.blocked_steps = blocked_steps
        self.context = context or {}

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        return {
            "plan_id": self.plan.id,
            "status": self.plan.status.value,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "blocked_steps": self.blocked_steps,
            "context": self.context,
        }


# ---------------------------------------------------------------------------
# AGENT EXECUTOR
# ---------------------------------------------------------------------------

class AgentExecutor:
    """
    Safe orchestration layer for NOVA agent plans.

    Responsibilities:

    - dependency-aware execution
    - deterministic execution ordering
    - tool allow-list enforcement
    - confirmation gates
    - execution state tracking
    - context propagation
    - mission cancellation
    - safe failure handling
    - dependency deadlock protection

    Tool handlers receive a private `_context` object containing:

    - plan objective
    - current step metadata
    - results from previously completed steps

    This allows later steps to consume actual results from earlier steps.
    """

    def __init__(
        self,
        auto_confirm: bool = False,
    ) -> None:
        self.auto_confirm = bool(
            auto_confirm
        )

    # ------------------------------------------------------------------
    # DEPENDENCY HELPERS
    # ------------------------------------------------------------------

    def _step_map(
        self,
        plan: AgentPlan,
    ) -> Dict[str, PlanStep]:
        return {
            step.id: step
            for step in plan.steps
        }

    def _dependencies_completed(
        self,
        step: PlanStep,
        step_map: Dict[str, PlanStep],
    ) -> bool:
        """
        Check whether every dependency has completed successfully.
        """

        for dependency_id in step.dependencies:

            dependency = step_map.get(
                dependency_id
            )

            if dependency is None:
                return False

            if (
                dependency.status
                != PlanStepStatus.COMPLETED
            ):
                return False

        return True

    def _has_failed_dependency(
        self,
        step: PlanStep,
        step_map: Dict[str, PlanStep],
    ) -> bool:
        """
        Check whether any dependency failed, was skipped,
        or no longer exists.
        """

        for dependency_id in step.dependencies:

            dependency = step_map.get(
                dependency_id
            )

            if dependency is None:
                return True

            if dependency.status in {
                PlanStepStatus.FAILED,
                PlanStepStatus.SKIPPED,
            }:
                return True

        return False

    # ------------------------------------------------------------------
    # TOOL VALIDATION
    # ------------------------------------------------------------------

    def _get_tool(
        self,
        step: PlanStep,
    ) -> ToolDefinition:
        """
        Resolve and validate a tool from NOVA's allow-list.
        """

        if not step.tool:
            raise ValueError(
                f"Step '{step.id}' has no tool assigned."
            )

        tool = get_tool(
            step.tool
        )

        if tool is None:
            raise ValueError(
                f"Tool '{step.tool}' is not registered."
            )

        if not tool.enabled:
            raise ValueError(
                f"Tool '{step.tool}' is disabled."
            )

        return tool

    def _requires_confirmation(
        self,
        tool: ToolDefinition,
    ) -> bool:
        """
        Determine whether a tool requires an explicit confirmation gate.
        """

        if not tool.requires_confirmation:
            return False

        return not self.auto_confirm

    # ------------------------------------------------------------------
    # CONTEXT BUILDING
    # ------------------------------------------------------------------

    def _build_step_context(
        self,
        step: PlanStep,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the private context exposed to a tool handler.

        The handler receives:

        - the overall plan objective
        - current step metadata
        - completed step results
        """

        completed_results: Dict[
            str,
            Any,
        ] = {}

        for key, value in context.items():

            if str(
                key
            ).startswith(
                "__"
            ):
                continue

            completed_results[
                key
            ] = value

        return {
            "plan_objective": context.get(
                "__plan_objective"
            ),
            "current_step": {
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "tool": step.tool,
            },
            "steps": completed_results,
        }

    # ------------------------------------------------------------------
    # SINGLE STEP EXECUTION
    # ------------------------------------------------------------------

    def execute_step(
        self,
        step: PlanStep,
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute one step through its registered tool handler.

        A tool without an explicit handler is rejected safely.
        """

        tool = self._get_tool(
            step
        )

        if self._requires_confirmation(
            tool
        ):
            raise PermissionError(
                "Confirmation required before executing "
                f"tool '{tool.name}'."
            )

        if tool.handler is None:
            raise NotImplementedError(
                f"Tool '{tool.name}' is registered but "
                "has no execution handler yet."
            )

        inputs = dict(
            step.inputs
        )

        inputs[
            "_context"
        ] = self._build_step_context(
            step=step,
            context=context,
        )

        return tool.handler(
            **inputs
        )

    # ------------------------------------------------------------------
    # EXECUTION STATE HELPERS
    # ------------------------------------------------------------------

    def _mark_remaining_steps_skipped(
        self,
        plan: AgentPlan,
        remaining: Set[str],
        blocked_steps: List[str],
        reason: str,
    ) -> None:
        """
        Mark all not-yet-started steps as skipped.
        """

        step_map = self._step_map(
            plan
        )

        for step_id in list(
            remaining
        ):
            step = step_map.get(
                step_id
            )

            if step is None:
                remaining.remove(
                    step_id
                )
                continue

            if step.status in {
                PlanStepStatus.COMPLETED,
                PlanStepStatus.FAILED,
                PlanStepStatus.SKIPPED,
            }:
                remaining.remove(
                    step_id
                )
                continue

            step.status = (
                PlanStepStatus.SKIPPED
            )

            step.error = reason

            if step.id not in blocked_steps:
                blocked_steps.append(
                    step.id
                )

            remaining.remove(
                step_id
            )

    def _public_context(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Remove executor-private metadata before returning execution data.
        """

        return {
            key: value
            for key, value in context.items()
            if not str(
                key
            ).startswith(
                "__"
            )
        }

    # ------------------------------------------------------------------
    # CANCELLATION
    # ------------------------------------------------------------------

    def _cancel_execution(
        self,
        plan: AgentPlan,
        completed_steps: List[str],
        failed_steps: List[str],
        blocked_steps: List[str],
        context: Dict[str, Any],
        remaining: Set[str],
        reason: str,
    ) -> ExecutionResult:
        """
        Stop an in-flight plan.

        Important:
        Completed results are preserved so Mission Control can still inspect
        everything that was successfully executed before STOP was requested.
        """

        self._mark_remaining_steps_skipped(
            plan=plan,
            remaining=remaining,
            blocked_steps=blocked_steps,
            reason=reason,
        )

        plan.status = (
            PlanStatus.CANCELLED
        )

        return ExecutionResult(
            plan=plan,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            blocked_steps=blocked_steps,
            context=self._public_context(
                context
            ),
        )

    # ------------------------------------------------------------------
    # PLAN EXECUTION
    # ------------------------------------------------------------------

    def execute(
        self,
        plan: AgentPlan,
        context: Dict[str, Any] | None = None,
        mission_id: str | None = None,
    ) -> ExecutionResult:
        """
        Execute a plan in dependency order.

        Results from completed steps are stored in context and made available
        to every downstream dependent step.

        Mission cancellation is cooperative:
        a running tool is allowed to finish, then the executor stops starting
        subsequent work.
        """

        if context is None:
            context = {}

        # --------------------------------------------------------------
        # Resolve mission identity.
        # --------------------------------------------------------------

        if not mission_id:

            mission_context = context.get(
                "mission"
            )

            if isinstance(
                mission_context,
                dict,
            ):
                mission_id = (
                    mission_context.get(
                        "mission_id"
                    )
                )

            if not mission_id:
                mission_id = (
                    context.get(
                        "mission_id"
                    )
                )

        normalized_mission_id = (
            _normalize_mission_id(
                mission_id
            )
        )

        if not normalized_mission_id:
            normalized_mission_id = None

        # --------------------------------------------------------------
        # Prepare private executor metadata.
        # --------------------------------------------------------------

        context[
            "__plan_objective"
        ] = plan.objective

        context[
            "__execution_status"
        ] = "RUNNING"

        context[
            "__execution_cancelled"
        ] = False

        context[
            "__execution_started_steps"
        ] = []

        context[
            "__execution_completed_steps"
        ] = []

        # --------------------------------------------------------------
        # Start plan.
        # --------------------------------------------------------------

        plan.status = (
            PlanStatus.RUNNING
        )

        step_map = self._step_map(
            plan
        )

        # Keep deterministic plan order.
        ordered_step_ids: List[str] = [
            step.id
            for step in plan.steps
        ]

        completed_steps: List[str] = []
        failed_steps: List[str] = []
        blocked_steps: List[str] = []

        remaining: Set[str] = {
            step.id
            for step in plan.steps
        }

        # --------------------------------------------------------------
        # Main scheduler.
        # --------------------------------------------------------------

        while remaining:

            # ----------------------------------------------------------
            # Mission cancellation before starting another scheduler pass.
            # ----------------------------------------------------------

            if (
                normalized_mission_id
                and is_mission_cancelled(
                    normalized_mission_id
                )
            ):

                context[
                    "__execution_status"
                ] = "CANCELLED"

                context[
                    "__execution_cancelled"
                ] = True

                result = (
                    self._cancel_execution(
                        plan=plan,
                        completed_steps=completed_steps,
                        failed_steps=failed_steps,
                        blocked_steps=blocked_steps,
                        context=context,
                        remaining=remaining,
                        reason=(
                            "Mission execution was stopped by the user."
                        ),
                    )
                )

                clear_mission_cancelled(
                    normalized_mission_id
                )

                return result

            progress = False

            # ----------------------------------------------------------
            # Evaluate steps in original plan order.
            # ----------------------------------------------------------

            for step_id in ordered_step_ids:

                if step_id not in remaining:
                    continue

                step = step_map[
                    step_id
                ]

                # ------------------------------------------------------
                # Cancellation immediately before a new step.
                # ------------------------------------------------------

                if (
                    normalized_mission_id
                    and is_mission_cancelled(
                        normalized_mission_id
                    )
                ):

                    context[
                        "__execution_status"
                    ] = "CANCELLED"

                    context[
                        "__execution_cancelled"
                    ] = True

                    result = (
                        self._cancel_execution(
                            plan=plan,
                            completed_steps=completed_steps,
                            failed_steps=failed_steps,
                            blocked_steps=blocked_steps,
                            context=context,
                            remaining=remaining,
                            reason=(
                                "Mission execution was stopped by the user."
                            ),
                        )
                    )

                    clear_mission_cancelled(
                        normalized_mission_id
                    )

                    return result

                # ------------------------------------------------------
                # Already handled step.
                # ------------------------------------------------------

                if step.status in {
                    PlanStepStatus.COMPLETED,
                    PlanStepStatus.FAILED,
                    PlanStepStatus.SKIPPED,
                }:

                    remaining.remove(
                        step.id
                    )

                    continue

                # ------------------------------------------------------
                # Failed or skipped dependency.
                # ------------------------------------------------------

                if self._has_failed_dependency(
                    step=step,
                    step_map=step_map,
                ):

                    step.status = (
                        PlanStepStatus.SKIPPED
                    )

                    step.error = (
                        "A dependency failed or "
                        "was skipped."
                    )

                    if step.id not in blocked_steps:
                        blocked_steps.append(
                            step.id
                        )

                    remaining.remove(
                        step.id
                    )

                    progress = True

                    continue

                # ------------------------------------------------------
                # Dependency not finished yet.
                # ------------------------------------------------------

                if not self._dependencies_completed(
                    step=step,
                    step_map=step_map,
                ):
                    continue

                # ------------------------------------------------------
                # Start step.
                # ------------------------------------------------------

                step.status = (
                    PlanStepStatus.RUNNING
                )

                started_steps = context.get(
                    "__execution_started_steps"
                )

                if isinstance(
                    started_steps,
                    list,
                ):
                    started_steps.append(
                        step.id
                    )

                try:

                    result = self.execute_step(
                        step=step,
                        context=context,
                    )

                    # --------------------------------------------------
                    # Preserve the raw real tool result.
                    # --------------------------------------------------

                    step.result = result

                    step.status = (
                        PlanStepStatus.COMPLETED
                    )

                    step.error = None

                    context[
                        step.id
                    ] = result

                    completed_steps.append(
                        step.id
                    )

                    completed_context_steps = (
                        context.get(
                            "__execution_completed_steps"
                        )
                    )

                    if isinstance(
                        completed_context_steps,
                        list,
                    ):
                        completed_context_steps.append(
                            step.id
                        )

                except PermissionError as exc:

                    step.status = (
                        PlanStepStatus.FAILED
                    )

                    step.error = str(
                        exc
                    )

                    failed_steps.append(
                        step.id
                    )

                except Exception as exc:

                    step.status = (
                        PlanStepStatus.FAILED
                    )

                    step.error = str(
                        exc
                    )

                    failed_steps.append(
                        step.id
                    )

                finally:

                    # The step has now been handled, regardless of outcome.
                    remaining.remove(
                        step.id
                    )

                    progress = True

                # ------------------------------------------------------
                # A STOP request may have arrived while this tool was
                # executing. Do not start another step.
                # ------------------------------------------------------

                if (
                    normalized_mission_id
                    and is_mission_cancelled(
                        normalized_mission_id
                    )
                ):

                    context[
                        "__execution_status"
                    ] = "CANCELLED"

                    context[
                        "__execution_cancelled"
                    ] = True

                    result = (
                        self._cancel_execution(
                            plan=plan,
                            completed_steps=completed_steps,
                            failed_steps=failed_steps,
                            blocked_steps=blocked_steps,
                            context=context,
                            remaining=remaining,
                            reason=(
                                "Mission execution was stopped by the user."
                            ),
                        )
                    )

                    clear_mission_cancelled(
                        normalized_mission_id
                    )

                    return result

            # ----------------------------------------------------------
            # Dependency deadlock / invalid dependency graph protection.
            # ----------------------------------------------------------

            if not progress:

                deadlock_reason = (
                    "Execution stopped because the dependency graph "
                    "could not make further progress."
                )

                for step_id in ordered_step_ids:

                    if step_id not in remaining:
                        continue

                    step = step_map[
                        step_id
                    ]

                    step.status = (
                        PlanStepStatus.SKIPPED
                    )

                    step.error = deadlock_reason

                    if step.id not in blocked_steps:
                        blocked_steps.append(
                            step.id
                        )

                    remaining.remove(
                        step.id
                    )

                context[
                    "__execution_status"
                ] = "FAILED"

                break

        # --------------------------------------------------------------
        # Final cancellation check.
        # --------------------------------------------------------------

        if (
            normalized_mission_id
            and is_mission_cancelled(
                normalized_mission_id
            )
        ):

            context[
                "__execution_status"
            ] = "CANCELLED"

            context[
                "__execution_cancelled"
            ] = True

            result = (
                self._cancel_execution(
                    plan=plan,
                    completed_steps=completed_steps,
                    failed_steps=failed_steps,
                    blocked_steps=blocked_steps,
                    context=context,
                    remaining=remaining,
                    reason=(
                        "Mission execution was stopped by the user."
                    ),
                )
            )

            clear_mission_cancelled(
                normalized_mission_id
            )

            return result

        # --------------------------------------------------------------
        # Determine final status.
        # --------------------------------------------------------------

        if failed_steps:
            plan.status = (
                PlanStatus.FAILED
            )

            context[
                "__execution_status"
            ] = "FAILED"

        elif blocked_steps:
            plan.status = (
                PlanStatus.FAILED
            )

            context[
                "__execution_status"
            ] = "FAILED"

        else:
            plan.status = (
                PlanStatus.COMPLETED
            )

            context[
                "__execution_status"
            ] = "COMPLETED"

        # --------------------------------------------------------------
        # Return only public execution context.
        # --------------------------------------------------------------

        public_context = (
            self._public_context(
                context
            )
        )

        return ExecutionResult(
            plan=plan,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            blocked_steps=blocked_steps,
            context=public_context,
        )


# ---------------------------------------------------------------------------
# SHARED EXECUTOR INSTANCE
# ---------------------------------------------------------------------------

agent_executor = AgentExecutor()