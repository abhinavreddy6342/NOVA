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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan.id,
            "status": self.plan.status.value,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "blocked_steps": self.blocked_steps,
            "context": self.context,
        }


class AgentExecutor:
    """
    Safe orchestration layer for NOVA agent plans.

    Responsibilities:
    - dependency-aware execution
    - tool allow-list enforcement
    - confirmation gates
    - execution state tracking
    - context propagation
    - safe failure handling

    Tool handlers receive a private `_context` object
    containing results from previously completed steps.
    """

    def __init__(
        self,
        auto_confirm: bool = False,
    ) -> None:
        self.auto_confirm = auto_confirm

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
        Check whether every dependency has completed.
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
        Check whether any dependency failed or was skipped.
        """

        for dependency_id in step.dependencies:
            dependency = step_map.get(
                dependency_id
            )

            if dependency is None:
                return True

            if dependency.status in (
                PlanStepStatus.FAILED,
                PlanStepStatus.SKIPPED,
            ):
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
        Resolve and validate a tool from the allow-list.
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
        Determine whether execution requires confirmation.
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
        Build the context exposed to a tool handler.

        The handler receives:
        - completed step results
        - current step metadata
        - the original plan objective
        """

        return {
            "plan_objective": (
                context.get(
                    "__plan_objective"
                )
            ),
            "current_step": {
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "tool": step.tool,
            },
            "steps": {
                key: value
                for key, value in context.items()
                if not key.startswith("__")
            },
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
                f"Confirmation required before executing "
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

        inputs["_context"] = (
            self._build_step_context(
                step,
                context,
            )
        )

        return tool.handler(
            **inputs
        )

    # ------------------------------------------------------------------
    # PLAN EXECUTION
    # ------------------------------------------------------------------

    def execute(
        self,
        plan: AgentPlan,
        context: Dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """
        Execute a plan in dependency order.

        Results from completed steps are stored in context
        and made available to later dependent steps.
        """

        if context is None:
            context = {}

        context["__plan_objective"] = (
            plan.objective
        )

        plan.status = (
            PlanStatus.RUNNING
        )

        step_map = self._step_map(
            plan
        )

        completed_steps: List[str] = []
        failed_steps: List[str] = []
        blocked_steps: List[str] = []

        remaining: Set[str] = {
            step.id
            for step in plan.steps
        }

        while remaining:
            progress = False

            for step_id in list(remaining):
                step = step_map[
                    step_id
                ]

                # ------------------------------------------------------
                # Failed dependency
                # ------------------------------------------------------

                if self._has_failed_dependency(
                    step,
                    step_map,
                ):
                    step.status = (
                        PlanStepStatus.SKIPPED
                    )

                    step.error = (
                        "A dependency failed or "
                        "was skipped."
                    )

                    blocked_steps.append(
                        step.id
                    )

                    remaining.remove(
                        step.id
                    )

                    progress = True

                    continue

                # ------------------------------------------------------
                # Wait for dependencies
                # ------------------------------------------------------

                if not self._dependencies_completed(
                    step,
                    step_map,
                ):
                    continue

                # ------------------------------------------------------
                # Run step
                # ------------------------------------------------------

                step.status = (
                    PlanStepStatus.RUNNING
                )

                try:
                    result = self.execute_step(
                        step,
                        context,
                    )

                    step.result = result
                    step.status = (
                        PlanStepStatus.COMPLETED
                    )

                    # --------------------------------------------------
                    # Make the result available to downstream steps.
                    # --------------------------------------------------

                    context[
                        step.id
                    ] = result

                    completed_steps.append(
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

                remaining.remove(
                    step.id
                )

                progress = True

            # ----------------------------------------------------------
            # Dependency deadlock protection.
            # ----------------------------------------------------------

            if not progress:
                for step_id in list(
                    remaining
                ):
                    step = step_map[
                        step_id
                    ]

                    step.status = (
                        PlanStepStatus.SKIPPED
                    )

                    step.error = (
                        "Execution stopped because "
                        "the dependency graph could "
                        "not make further progress."
                    )

                    blocked_steps.append(
                        step.id
                    )

                    remaining.remove(
                        step.id
                    )

        # --------------------------------------------------------------
        # Determine final plan status.
        # --------------------------------------------------------------

        if failed_steps:
            plan.status = (
                PlanStatus.FAILED
            )

        elif blocked_steps:
            plan.status = (
                PlanStatus.FAILED
            )

        else:
            plan.status = (
                PlanStatus.COMPLETED
            )

        # Do not expose internal metadata.
        public_context = {
            key: value
            for key, value in context.items()
            if not key.startswith("__")
        }

        return ExecutionResult(
            plan=plan,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            blocked_steps=blocked_steps,
            context=public_context,
        )


agent_executor = AgentExecutor()