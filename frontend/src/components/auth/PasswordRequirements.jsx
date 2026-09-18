import React from "react";
import { Check, X } from "lucide-react";

const requirements = [
  {
    key: "length",
    label: "8–128 characters",
    test: (password) =>
      password.length >= 8 && password.length <= 128,
  },
  {
    key: "uppercase",
    label: "One uppercase letter",
    test: (password) => /[A-Z]/.test(password),
  },
  {
    key: "lowercase",
    label: "One lowercase letter",
    test: (password) => /[a-z]/.test(password),
  },
  {
    key: "number",
    label: "One number",
    test: (password) => /\d/.test(password),
  },
  {
    key: "special",
    label: "One special character",
    test: (password) => /[^A-Za-z0-9]/.test(password),
  },
];

export default function PasswordRequirements({
  password = "",
  show = true,
}) {
  if (!show) {
    return null;
  }

  return (
    <div
      className="nova-password-requirements"
      aria-live="polite"
    >
      <div className="nova-password-requirements-title">
        Password requirements
      </div>

      <div className="nova-password-requirements-list">
        {requirements.map((requirement) => {
          const valid = requirement.test(password);

          return (
            <div
              key={requirement.key}
              className={`nova-password-requirement ${
                valid ? "is-valid" : "is-invalid"
              }`}
            >
              <span className="nova-password-requirement-icon">
                {valid ? (
                  <Check size={12} strokeWidth={2.5} />
                ) : (
                  <X size={12} strokeWidth={2.5} />
                )}
              </span>

              <span>{requirement.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function validatePassword(password = "") {
  return requirements.every((requirement) =>
    requirement.test(password)
  );
}