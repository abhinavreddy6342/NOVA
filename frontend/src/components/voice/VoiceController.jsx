import { useCallback, useEffect, useRef, useState } from "react";

function emitAvatarState(
  state,
  audioLevel = 0,
) {
  window.dispatchEvent(
    new CustomEvent("nova:avatar-state", {
      detail: {
        state,
        audioLevel,
        timestamp: Date.now(),
      },
    }),
  );
}

export default function VoiceController() {
  const [isSpeaking, setIsSpeaking] =
    useState(false);

  const [isSupported, setIsSupported] =
    useState(true);

  const utteranceRef =
    useRef(null);

  const animationFrameRef =
    useRef(null);

  const audioContextRef =
    useRef(null);

  const analyserRef =
    useRef(null);

  const sourceRef =
    useRef(null);

  const audioElementRef =
    useRef(null);

  const lastLevelRef =
    useRef(0);

  const stopAudioAnalysis =
    useCallback(() => {
      if (
        animationFrameRef.current
      ) {
        cancelAnimationFrame(
          animationFrameRef.current,
        );

        animationFrameRef.current =
          null;
      }

      if (sourceRef.current) {
        try {
          sourceRef.current.disconnect();
        } catch {
          // already disconnected
        }

        sourceRef.current = null;
      }

      analyserRef.current = null;

      lastLevelRef.current = 0;

      emitAvatarState(
        "idle",
        0,
      );
    }, []);

  const startAudioAnalysis =
    useCallback(
      async (audioElement) => {
        if (!audioElement) {
          return;
        }

        try {
          const AudioContext =
            window.AudioContext ||
            window.webkitAudioContext;

          if (!AudioContext) {
            return;
          }

          if (
            !audioContextRef.current
          ) {
            audioContextRef.current =
              new AudioContext();
          }

          const context =
            audioContextRef.current;

          if (
            context.state ===
            "suspended"
          ) {
            await context.resume();
          }

          /*
           * Create the analyser only once
           * for this audio element.
           */
          if (!sourceRef.current) {
            sourceRef.current =
              context.createMediaElementSource(
                audioElement,
              );

            analyserRef.current =
              context.createAnalyser();

            analyserRef.current.fftSize =
              256;

            analyserRef.current.smoothingTimeConstant =
              0.78;

            sourceRef.current.connect(
              analyserRef.current,
            );

            analyserRef.current.connect(
              context.destination,
            );
          }

          const analyser =
            analyserRef.current;

          const data =
            new Uint8Array(
              analyser.frequencyBinCount,
            );

          const updateLevel = () => {
            if (
              !analyserRef.current ||
              !audioElementRef.current ||
              audioElementRef.current.paused ||
              audioElementRef.current.ended
            ) {
              stopAudioAnalysis();
              return;
            }

            analyser.getByteFrequencyData(
              data,
            );

            let sum = 0;

            for (
              let i = 0;
              i < data.length;
              i += 1
            ) {
              sum += data[i];
            }

            const average =
              sum / data.length;

            /*
             * Normalize into 0..1.
             *
             * The multiplier makes normal speech
             * visually useful without making the
             * orb excessively reactive.
             */
            const rawLevel = Math.min(
              1,
              average / 110,
            );

            /*
             * Smooth the visual response.
             */
            const smoothedLevel =
              lastLevelRef.current *
                0.72 +
              rawLevel * 0.28;

            lastLevelRef.current =
              smoothedLevel;

            emitAvatarState(
              "speaking",
              smoothedLevel,
            );

            animationFrameRef.current =
              requestAnimationFrame(
                updateLevel,
              );
          };

          updateLevel();
        } catch (error) {
          console.error(
            "NOVA audio analysis error:",
            error,
          );
        }
      },
      [stopAudioAnalysis],
    );

  const speakWithBrowserTTS =
    useCallback(
      (text) => {
        if (
          typeof window ===
            "undefined" ||
          !(
            "speechSynthesis" in
            window
          )
        ) {
          setIsSupported(false);

          return;
        }

        window.speechSynthesis.cancel();

        const utterance =
          new SpeechSynthesisUtterance(
            text,
          );

        utterance.rate = 1;
        utterance.pitch = 1;
        utterance.volume = 1;

        utterance.onstart = () => {
          setIsSpeaking(true);

          emitAvatarState(
            "speaking",
            0.35,
          );

          /*
           * Browser speechSynthesis does NOT
           * provide the actual speaker waveform.
           *
           * Therefore this is a smooth fallback
           * envelope, not fake "measured" audio.
           */
          const startedAt =
            performance.now();

          const animateSpeech =
            () => {
              if (
                !utteranceRef.current ||
                !isSpeaking
              ) {
                return;
              }

              const elapsed =
                performance.now() -
                startedAt;

              const rhythm =
                0.34 +
                Math.sin(
                  elapsed * 0.016,
                ) *
                  0.09 +
                Math.sin(
                  elapsed * 0.037,
                ) *
                  0.055;

              const level =
                Math.max(
                  0.12,
                  Math.min(
                    0.6,
                    rhythm,
                  ),
                );

              emitAvatarState(
                "speaking",
                level,
              );

              animationFrameRef.current =
                requestAnimationFrame(
                  animateSpeech,
                );
            };

          /*
           * Start on the next frame so React
           * has updated speaking state.
           */
          requestAnimationFrame(
            animateSpeech,
          );
        };

        utterance.onend = () => {
          setIsSpeaking(false);

          utteranceRef.current =
            null;

          if (
            animationFrameRef.current
          ) {
            cancelAnimationFrame(
              animationFrameRef.current,
            );

            animationFrameRef.current =
              null;
          }

          emitAvatarState(
            "idle",
            0,
          );
        };

        utterance.onerror = (
          event,
        ) => {
          console.error(
            "NOVA speech synthesis error:",
            event,
          );

          setIsSpeaking(false);

          utteranceRef.current =
            null;

          if (
            animationFrameRef.current
          ) {
            cancelAnimationFrame(
              animationFrameRef.current,
            );

            animationFrameRef.current =
              null;
          }

          emitAvatarState(
            "idle",
            0,
          );
        };

        utteranceRef.current =
          utterance;

        window.speechSynthesis.speak(
          utterance,
        );
      },
      [isSpeaking],
    );

  useEffect(() => {
    if (
      typeof window ===
        "undefined" ||
      !(
        "speechSynthesis" in
        window
      )
    ) {
      setIsSupported(false);

      return;
    }

    const handleSpeak = (
      event,
    ) => {
      const text =
        event.detail?.text?.trim();

      if (!text) {
        return;
      }

      /*
       * Stop any current browser speech.
       */
      window.speechSynthesis.cancel();

      stopAudioAnalysis();

      speakWithBrowserTTS(text);
    };

    const handleStop = () => {
      if (
        "speechSynthesis" in
        window
      ) {
        window.speechSynthesis.cancel();
      }

      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current.currentTime =
          0;
      }

      setIsSpeaking(false);

      utteranceRef.current =
        null;

      stopAudioAnalysis();
    };

    /*
     * Existing NOVA text-to-speech event.
     */
    window.addEventListener(
      "nova:speak",
      handleSpeak,
    );

    /*
     * Stop speech event.
     */
    window.addEventListener(
      "nova:tts-stop",
      handleStop,
    );

    /*
     * Future real-audio TTS event.
     *
     * Example:
     *
     * window.dispatchEvent(
     *   new CustomEvent("nova:speak-audio", {
     *     detail: { src: "/audio/nova.wav" }
     *   })
     * );
     */
    const handleSpeakAudio = async (
      event,
    ) => {
      const src =
        event.detail?.src;

      if (!src) {
        return;
      }

      handleStop();

      const audio =
        new Audio();

      audioElementRef.current =
        audio;

      audio.preload = "auto";
      audio.src = src;

      audio.onplay = () => {
        setIsSpeaking(true);

        emitAvatarState(
          "speaking",
          0.2,
        );

        startAudioAnalysis(
          audio,
        );
      };

      audio.onended = () => {
        setIsSpeaking(false);

        stopAudioAnalysis();
      };

      audio.onerror = () => {
        console.error(
          "NOVA audio playback failed.",
        );

        setIsSpeaking(false);

        stopAudioAnalysis();
      };

      try {
        await audio.play();
      } catch (error) {
        console.error(
          "NOVA audio playback was blocked:",
          error,
        );

        setIsSpeaking(false);

        stopAudioAnalysis();
      }
    };

    window.addEventListener(
      "nova:speak-audio",
      handleSpeakAudio,
    );

    /*
     * External code can provide a ready-made
     * HTMLAudioElement in the future.
     */
    const handleAttachAudio =
      (event) => {
        const audio =
          event.detail?.audio;

        if (
          !audio ||
          !(
            audio instanceof
            HTMLAudioElement
          )
        ) {
          return;
        }

        audioElementRef.current =
          audio;

        startAudioAnalysis(audio);
      };

    window.addEventListener(
      "nova:attach-audio",
      handleAttachAudio,
    );

    return () => {
      window.removeEventListener(
        "nova:speak",
        handleSpeak,
      );

      window.removeEventListener(
        "nova:tts-stop",
        handleStop,
      );

      window.removeEventListener(
        "nova:speak-audio",
        handleSpeakAudio,
      );

      window.removeEventListener(
        "nova:attach-audio",
        handleAttachAudio,
      );

      handleStop();

      if (
        audioContextRef.current
      ) {
        audioContextRef.current
          .close()
          .catch(() => {});
      }
    };
  }, [
    speakWithBrowserTTS,
    startAudioAnalysis,
    stopAudioAnalysis,
  ]);

  return (
    <div
      className="nova-voice-runtime"
      data-speaking={isSpeaking}
      data-supported={isSupported}
      aria-hidden="true"
    />
  );
}

export function speakNova(text) {
  if (
    typeof window ===
      "undefined" ||
    !text?.trim()
  ) {
    return;
  }

  window.dispatchEvent(
    new CustomEvent("nova:speak", {
      detail: {
        text: text.trim(),
      },
    }),
  );
}

export function speakNovaAudio(
  src,
) {
  if (
    typeof window ===
      "undefined" ||
    !src
  ) {
    return;
  }

  window.dispatchEvent(
    new CustomEvent(
      "nova:speak-audio",
      {
        detail: {
          src,
        },
      },
    ),
  );
}

export function stopNovaSpeaking() {
  if (
    typeof window !==
      "undefined"
  ) {
    window.dispatchEvent(
      new CustomEvent(
        "nova:tts-stop",
      ),
    );
  }
}