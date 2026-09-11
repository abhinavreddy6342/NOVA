import { motion } from "framer-motion";
import { Bot, User } from "lucide-react";

function ChatMessage({ role, content }) {
  const isUser = role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`nova-message ${isUser ? "nova-message-user" : "nova-message-assistant"}`}
    >
      <div className="nova-message-icon">
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>

      <div className="nova-message-content">
        <div className="nova-message-role">
          {isUser ? "YOU" : "NOVA"}
        </div>

        <div className="nova-message-text">
          {content}
        </div>
      </div>
    </motion.div>
  );
}

export default ChatMessage;