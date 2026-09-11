import { motion } from "framer-motion";

const STATE_LABELS = {
  IDLE: "SYSTEM IDLE",
  THINKING: "THINKING",
  ANALYZING: "ANALYZING",
  RESPONDING: "RESPONDING",
  COMPLETE: "COMPLETE",
  ERROR: "ERROR",
};

function AIState({ state = "IDLE" }) {
  const label = STATE_LABELS[state] || state;

  return (
    <motion.div
      className={`ai-state ai-state-${state.toLowerCase()}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.25 }}
    >
      <span className="ai-state-indicator" />
      <span>{label}</span>
    </motion.div>
  );
}

export default AIState;