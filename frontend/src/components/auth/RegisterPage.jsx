import React, { useMemo, useState } from "react";
import LoginBackground3D from "./LoginBackground3D";
import PasswordRequirements, {
  validatePassword,
} from "./PasswordRequirements";

function validateGmail(value) {
  const email = value.trim().toLowerCase();

  if (!email) {
    return "Email address is required.";
  }

  const gmailPattern =
    /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@gmail\.com$/i;

  if (!gmailPattern.test(email)) {
    return "Enter a valid Gmail address.";
  }

  return "";
}

export default function RegisterPage({
  onRegister,
  onBackToLogin,
  isLoading = false,
  authError = "",
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [emailTouched, setEmailTouched] =
    useState(false);

  const [passwordTouched, setPasswordTouched] =
    useState(false);

  const [confirmTouched, setConfirmTouched] =
    useState(false);

  const [localError, setLocalError] =
    useState("");

  const normalizedEmail =
    email.trim().toLowerCase();

  const emailError = useMemo(
    () => validateGmail(email),
    [email]
  );

  const passwordValid = useMemo(
    () => validatePassword(password),
    [password]
  );

  const confirmValid =
    password.length > 0 &&
    confirmPassword.length > 0 &&
    password === confirmPassword;

  const formValid =
    !emailError &&
    normalizedEmail.length > 0 &&
    passwordValid &&
    confirmValid;

  const currentError =
    authError || localError;

  const handleSubmit = async (event) => {
    event.preventDefault();

    setEmailTouched(true);
    setPasswordTouched(true);
    setConfirmTouched(true);
    setLocalError("");

    const currentEmailError =
      validateGmail(email);

    if (currentEmailError) {
      setLocalError(currentEmailError);
      return;
    }

    if (!validatePassword(password)) {
      setLocalError(
        "Password does not meet the required conditions."
      );
      return;
    }

    if (password !== confirmPassword) {
      setLocalError(
        "Passwords do not match."
      );
      return;
    }

    if (typeof onRegister !== "function") {
      setLocalError(
        "Registration is not available."
      );
      return;
    }

    try {
      await onRegister({
        email: normalizedEmail,
        password,
      });
    } catch (error) {
      setLocalError(
        error?.message ||
          "Unable to create your account. Please try again."
      );
    }
  };

  const handleEmailChange = (event) => {
    setEmail(event.target.value);

    if (localError) {
      setLocalError("");
    }
  };

  const handlePasswordChange = (event) => {
    setPassword(event.target.value);

    if (localError) {
      setLocalError("");
    }
  };

  const handleConfirmChange = (event) => {
    setConfirmPassword(event.target.value);

    if (localError) {
      setLocalError("");
    }
  };

  const handleBackToLogin = () => {
    if (
      typeof onBackToLogin === "function"
    ) {
      onBackToLogin();
    }
  };

  return (
    <main
      className="nova-auth-page"
      aria-label="NOVA account registration"
    >
      <LoginBackground3D />

      <section className="nova-auth-shell nova-auth-register-shell">
        <div className="nova-auth-brand">
          <div
            className="nova-auth-brand-mark"
            aria-hidden="true"
          >
            <svg
              viewBox="0 0 48 48"
              role="presentation"
              focusable="false"
            >
              <path
                d="M24 5l2.7 9.3L36 17l-9.3 2.7L24 29l-2.7-9.3L12 17l9.3-2.7L24 5Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              <path
                d="M37.5 29.5l1.4 4.6 4.6 1.4-4.6 1.4-1.4 4.6-1.4-4.6-4.6-1.4 4.6-1.4 1.4-4.6Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <div className="nova-auth-wordmark">
            NOVA
          </div>

          <div className="nova-auth-brand-subtitle">
            SOVEREIGN INDUSTRIAL INTELLIGENCE
          </div>

          <div className="nova-auth-workspace-status">
            <span
              className="nova-auth-status-dot"
              aria-hidden="true"
            />
            LOCAL INTELLIGENCE WORKSPACE
          </div>
        </div>

        <div className="nova-auth-card">
          <div className="nova-auth-card-inner">
            <header className="nova-auth-heading">
              <h1>CREATE ACCOUNT</h1>

              <p>
                Create your secure sovereign
                workspace identity.
              </p>
            </header>

            <form
              onSubmit={handleSubmit}
              noValidate
            >
              <div className="nova-auth-field">
                <div className="nova-auth-field-header">
                  <label htmlFor="nova-register-email">
                    Gmail address
                  </label>
                </div>

                <div
                  className={[
                    "nova-auth-input-wrap",
                    emailTouched &&
                    emailError
                      ? "is-invalid"
                      : "",
                    emailTouched &&
                    !emailError &&
                    email
                      ? "is-valid"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span
                    className="nova-auth-input-icon"
                    aria-hidden="true"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      focusable="false"
                    >
                      <rect
                        x="3.5"
                        y="5"
                        width="17"
                        height="14"
                        rx="2.2"
                      />

                      <path d="m5.2 7 6.8 5.2L18.8 7" />
                    </svg>
                  </span>

                  <input
                    id="nova-register-email"
                    name="email"
                    type="email"
                    inputMode="email"
                    autoComplete="email"
                    value={email}
                    onChange={handleEmailChange}
                    onBlur={() =>
                      setEmailTouched(true)
                    }
                    placeholder="Enter your Gmail address"
                    aria-invalid={Boolean(
                      emailTouched &&
                        emailError
                    )}
                    aria-describedby="nova-register-email-error"
                    disabled={isLoading}
                  />
                </div>

                <div
                  id="nova-register-email-error"
                  className="nova-auth-validation"
                  aria-live="polite"
                >
                  {emailTouched &&
                  emailError
                    ? emailError
                    : ""}
                </div>
              </div>

              <div className="nova-auth-field">
                <div className="nova-auth-field-header">
                  <label htmlFor="nova-register-password">
                    Password
                  </label>
                </div>

                <div
                  className={[
                    "nova-auth-input-wrap",
                    passwordTouched &&
                    !passwordValid
                      ? "is-invalid"
                      : "",
                    passwordTouched &&
                    passwordValid
                      ? "is-valid"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span
                    className="nova-auth-input-icon"
                    aria-hidden="true"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      focusable="false"
                    >
                      <rect
                        x="5.2"
                        y="10"
                        width="13.6"
                        height="10"
                        rx="2"
                      />

                      <path d="M8 10V7.7a4 4 0 0 1 8 0V10" />
                    </svg>
                  </span>

                  <input
                    id="nova-register-password"
                    name="password"
                    type={
                      showPassword
                        ? "text"
                        : "password"
                    }
                    autoComplete="new-password"
                    value={password}
                    onChange={handlePasswordChange}
                    onBlur={() =>
                      setPasswordTouched(true)
                    }
                    placeholder="Create your password"
                    aria-invalid={Boolean(
                      passwordTouched &&
                        !passwordValid
                    )}
                    aria-describedby="nova-register-password-rules"
                    disabled={isLoading}
                  />

                  <button
                    type="button"
                    className="nova-auth-password-toggle"
                    onClick={() =>
                      setShowPassword(
                        (value) => !value
                      )
                    }
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    aria-pressed={showPassword}
                    disabled={isLoading}
                  >
                    {showPassword ? (
                      <svg
                        viewBox="0 0 24 24"
                        focusable="false"
                      >
                        <path d="M3.5 3.5 20.5 20.5" />
                        <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
                        <path d="M9.8 5.2A11.8 11.8 0 0 1 12 5c5.1 0 8.7 4.3 9.6 6-.4.8-1.5 2.2-3.3 3.4" />
                        <path d="M6.1 6.1C4.5 7.3 3.2 9 2.4 11c.9 1.8 4.5 6 9.6 6 1 0 2-.2 2.9-.5" />
                      </svg>
                    ) : (
                      <svg
                        viewBox="0 0 24 24"
                        focusable="false"
                      >
                        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />

                        <circle
                          cx="12"
                          cy="12"
                          r="2.7"
                        />
                      </svg>
                    )}
                  </button>
                </div>

                <div
                  id="nova-register-password-rules"
                  className="nova-auth-password-rules"
                >
                  <PasswordRequirements
                    password={password}
                    show={true}
                  />
                </div>
              </div>

              <div className="nova-auth-field">
                <div className="nova-auth-field-header">
                  <label htmlFor="nova-register-confirm-password">
                    Confirm password
                  </label>
                </div>

                <div
                  className={[
                    "nova-auth-input-wrap",
                    confirmTouched &&
                    !confirmValid
                      ? "is-invalid"
                      : "",
                    confirmTouched &&
                    confirmValid
                      ? "is-valid"
                      : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  <span
                    className="nova-auth-input-icon"
                    aria-hidden="true"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      focusable="false"
                    >
                      <rect
                        x="5.2"
                        y="10"
                        width="13.6"
                        height="10"
                        rx="2"
                      />

                      <path d="M8 10V7.7a4 4 0 0 1 8 0V10" />
                    </svg>
                  </span>

                  <input
                    id="nova-register-confirm-password"
                    name="confirmPassword"
                    type={
                      showConfirmPassword
                        ? "text"
                        : "password"
                    }
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={handleConfirmChange}
                    onBlur={() =>
                      setConfirmTouched(true)
                    }
                    placeholder="Re-enter your password"
                    aria-invalid={Boolean(
                      confirmTouched &&
                        !confirmValid
                    )}
                    aria-describedby="nova-register-confirm-error"
                    disabled={isLoading}
                  />

                  <button
                    type="button"
                    className="nova-auth-password-toggle"
                    onClick={() =>
                      setShowConfirmPassword(
                        (value) => !value
                      )
                    }
                    aria-label={
                      showConfirmPassword
                        ? "Hide confirmation password"
                        : "Show confirmation password"
                    }
                    aria-pressed={
                      showConfirmPassword
                    }
                    disabled={isLoading}
                  >
                    {showConfirmPassword ? (
                      <svg
                        viewBox="0 0 24 24"
                        focusable="false"
                      >
                        <path d="M3.5 3.5 20.5 20.5" />
                        <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
                        <path d="M9.8 5.2A11.8 11.8 0 0 1 12 5c5.1 0 8.7 4.3 9.6 6-.4.8-1.5 2.2-3.3 3.4" />
                        <path d="M6.1 6.1C4.5 7.3 3.2 9 2.4 11c.9 1.8 4.5 6 9.6 6 1 0 2-.2 2.9-.5" />
                      </svg>
                    ) : (
                      <svg
                        viewBox="0 0 24 24"
                        focusable="false"
                      >
                        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />

                        <circle
                          cx="12"
                          cy="12"
                          r="2.7"
                        />
                      </svg>
                    )}
                  </button>
                </div>

                <div
                  id="nova-register-confirm-error"
                  className="nova-auth-validation"
                  aria-live="polite"
                >
                  {confirmTouched &&
                  !confirmValid
                    ? "Passwords do not match."
                    : ""}
                </div>
              </div>

              {currentError ? (
                <div
                  className="nova-auth-form-error"
                  role="alert"
                >
                  <span
                    className="nova-auth-error-dot"
                    aria-hidden="true"
                  />

                  {currentError}
                </div>
              ) : null}

              <button
                type="submit"
                className="nova-auth-submit"
                disabled={
                  !formValid ||
                  isLoading
                }
              >
                <span>
                  {isLoading
                    ? "CREATING ACCOUNT..."
                    : "CREATE ACCOUNT"}
                </span>

                {!isLoading ? (
                  <svg
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                    focusable="false"
                  >
                    <path d="M5 12h13" />
                    <path d="m13 6 6 6-6 6" />
                  </svg>
                ) : (
                  <span
                    className="nova-auth-loader"
                    aria-hidden="true"
                  />
                )}
              </button>
            </form>
          </div>
        </div>

        <div className="nova-auth-create">
          <span>
            Already have an account?
          </span>

          <button
            type="button"
            onClick={handleBackToLogin}
            disabled={isLoading}
          >
            SIGN IN
          </button>
        </div>

        <div className="nova-auth-secure">
          <span className="nova-auth-secure-line" />

          <span
            className="nova-auth-secure-icon"
            aria-hidden="true"
          >
            <svg
              viewBox="0 0 24 24"
              focusable="false"
            >
              <rect
                x="5"
                y="10"
                width="14"
                height="10"
                rx="2"
              />

              <path d="M8 10V7.8a4 4 0 0 1 8 0V10" />
            </svg>
          </span>

          <span>
            LOCAL / SECURE
          </span>

          <span className="nova-auth-secure-line" />
        </div>
      </section>
    </main>
  );
}