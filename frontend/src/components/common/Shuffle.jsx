import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_CHARS =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

function shuffleString(text, chars, seed) {
  let output = "";

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];

    if (char === " ") {
      output += " ";
      continue;
    }

    const index = Math.floor(
      Math.abs(Math.sin(seed + i * 12.9898)) * chars.length,
    );

    output += chars[index];
  }

  return output;
}

export default function Shuffle({
  text = "",
  shuffleDirection = "right",
  duration = 0.35,
  animationMode = "evenodd",
  shuffleTimes = 1,
  ease = "power3.out",
  stagger = 0.03,
  threshold = 0.1,
  triggerOnce = true,
  triggerOnHover = true,
  respectReducedMotion = true,
  className = "",
  chars = DEFAULT_CHARS,
}) {
  const containerRef = useRef(null);
  const animationRef = useRef(null);
  const hasTriggeredRef = useRef(false);

  const characters = useMemo(() => Array.from(text), [text]);

  const [displayText, setDisplayText] = useState(text);

  const reducedMotion = useMemo(() => {
    if (!respectReducedMotion || typeof window === "undefined") {
      return false;
    }

    return window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
  }, [respectReducedMotion]);

  const clearAnimation = useCallback(() => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  }, []);

  const runShuffle = useCallback(() => {
    clearAnimation();

    if (!text || reducedMotion) {
      setDisplayText(text);
      return;
    }

    const startTime = performance.now();
    const totalDuration = Math.max(duration, 0.05) * 1000;
    const totalRounds = Math.max(1, shuffleTimes);

    const directionMultiplier =
      shuffleDirection === "left" ? -1 : 1;

    const tick = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(
        elapsed / totalDuration,
        1,
      );

      const easedProgress =
        ease === "power3.out"
          ? 1 - Math.pow(1 - progress, 3)
          : progress;

      const frame = characters.map((char, index) => {
        if (char === " ") {
          return " ";
        }

        const characterDelay =
          (index * stagger * 1000) /
          Math.max(characters.length, 1);

        const localProgress = Math.max(
          0,
          Math.min(
            1,
            (elapsed -
              characterDelay * directionMultiplier) /
              totalDuration,
          ),
        );

        const localEased =
          ease === "power3.out"
            ? 1 - Math.pow(1 - localProgress, 3)
            : localProgress;

        if (localEased >= 1) {
          return char;
        }

        const revealPoint = Math.floor(
          localEased * (totalRounds + 1),
        );

        if (revealPoint >= totalRounds) {
          return char;
        }

        return shuffleString(
          char,
          chars,
          index * 31.7 +
            Math.floor(elapsed / 45) +
            revealPoint * 17.13,
        );
      });

      setDisplayText(frame.join(""));

      if (
        progress < 1 ||
        easedProgress < 1
      ) {
        animationRef.current =
          requestAnimationFrame(tick);
      } else {
        setDisplayText(text);
        animationRef.current = null;
      }
    };

    setDisplayText(
      shuffleString(
        text,
        chars,
        Math.random() * 1000,
      ),
    );

    animationRef.current =
      requestAnimationFrame(tick);
  }, [
    chars,
    characters,
    clearAnimation,
    duration,
    ease,
    reducedMotion,
    shuffleDirection,
    shuffleTimes,
    stagger,
    text,
  ]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !containerRef.current
    ) {
      return undefined;
    }

    const node = containerRef.current;

    if (
      triggerOnce &&
      hasTriggeredRef.current
    ) {
      return undefined;
    }

    const observer =
      new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            hasTriggeredRef.current = true;

            runShuffle();

            if (triggerOnce) {
              observer.disconnect();
            }
          }
        },
        {
          threshold,
        },
      );

    observer.observe(node);

    return () => {
      observer.disconnect();
      clearAnimation();
    };
  }, [
    clearAnimation,
    runShuffle,
    threshold,
    triggerOnce,
  ]);

  const handleMouseEnter = () => {
    if (triggerOnHover) {
      runShuffle();
    }
  };

  return (
    <span
      ref={containerRef}
      className={className}
      onMouseEnter={handleMouseEnter}
      data-animation-mode={animationMode}
    >
      {displayText}
    </span>
  );
}