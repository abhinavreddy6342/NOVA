import { motion } from "framer-motion";
import Shuffle from "./Shuffle";

export default function AnimatedShuffle({
  text,
  duration = 0.35,
  delay = 0,
  className = "",
  ...shuffleProps
}) {
  return (
    <motion.span
      className={`animated-shuffle ${className}`}
      initial={{
        opacity: 0,
        y: 10,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        duration,
        delay,
        ease: [0.22, 1, 0.36, 1],
      }}
      style={{
        display: "inline-block",
      }}
    >
      <Shuffle
        text={text}
        duration={0.35}
        shuffleDirection="right"
        animationMode="evenodd"
        shuffleTimes={1}
        ease="power3.out"
        stagger={0.03}
        threshold={0.1}
        triggerOnce={true}
        triggerOnHover={true}
        respectReducedMotion={true}
        {...shuffleProps}
      />
    </motion.span>
  );
}