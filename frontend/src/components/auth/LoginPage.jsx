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

export default function LoginPage({
  onLogin,
  onForgotPassword,
  onCreateAccount,
  isLoading = false,
  authError = "",
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [emailTouched, setEmailTouched] = useState(false);
  const [passwordTouched, setPasswordTouched] = useState(false);
  const [localError, setLocalError] = useState("");

  const normalizedEmail = email.trim().toLowerCase();

  const emailError = useMemo(
    () => validateGmail(email),
    [email]
  );

  const passwordValid = useMemo(
    () => validatePassword(password),
    [password]
  );

  const formValid =
    normalizedEmail.length > 0 &&
    !emailError &&
    passwordValid;

  const currentError = authError || localError;

  const handleSubmit = async (event) => {
    event.preventDefault();

    setEmailTouched(true);
    setPasswordTouched(true);
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

    if (typeof onLogin !== "function") {
      setLocalError(
        "Authentication is not available."
      );
      return;
    }

    try {
      await onLogin({
        email: normalizedEmail,
        password,
        rememberMe,
      });
    } catch (error) {
      setLocalError(
        error?.message ||
          "Unable to sign in. Please try again."
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

  const handleForgotPassword = () => {
    if (
      typeof onForgotPassword === "function"
    ) {
      onForgotPassword();
    }
  };

  const handleCreateAccount = () => {
    if (
      typeof onCreateAccount === "function"
    ) {
      onCreateAccount();
    }
  };

  return (
    <main
      className="nova-auth-page"
      aria-label="NOVA sign in"
    >
      <LoginBackground3D />

      <section className="nova-auth-shell">
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
              <h1>WELCOME BACK</h1>

              <p>
                Sign in to continue to your
                sovereign workspace.
              </p>
            </header>

            <form
              onSubmit={handleSubmit}
              noValidate
            >
              <div className="nova-auth-field">
                <div className="nova-auth-field-header">
                  <label htmlFor="nova-login-email">
                    Email address
                  </label>
                </div>

                <div
                  className={[
                    "nova-auth-input-wrap",
                    emailTouched && emailError
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
                    id="nova-login-email"
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
                    aria-describedby="nova-login-email-error"
                    disabled={isLoading}
                  />
                </div>

                <div
                  id="nova-login-email-error"
                  className="nova-auth-validation"
                  aria-live="polite"
                >
                  {emailTouched && emailError
                    ? emailError
                    : ""}
                </div>
              </div>

              <div className="nova-auth-field">
                <div className="nova-auth-field-header">
                  <label htmlFor="nova-login-password">
                    Password
                  </label>

                  <button
                    type="button"
                    className="nova-auth-forgot"
                    onClick={
                      handleForgotPassword
                    }
                    disabled={isLoading}
                  >
                    Forgot password?
                  </button>
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
                    id="nova-login-password"
                    name="password"
                    type={
                      showPassword
                        ? "text"
                        : "password"
                    }
                    autoComplete="current-password"
                    value={password}
                    onChange={handlePasswordChange}
                    onBlur={() =>
                      setPasswordTouched(true)
                    }
                    placeholder="Enter your password"
                    aria-invalid={Boolean(
                      passwordTouched &&
                        !passwordValid
                    )}
                    aria-describedby="nova-login-password-rules"
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
                  id="nova-login-password-rules"
                  className="nova-auth-password-rules"
                >
                  <PasswordRequirements
                    password={password}
                    show={true}
                  />
                </div>

                <div
                  className="nova-auth-validation"
                  aria-live="polite"
                >
                  {passwordTouched &&
                  !passwordValid
                    ? "Password does not meet the required conditions."
                    : ""}
                </div>
              </div>

              <div className="nova-auth-options">
                <label className="nova-auth-checkbox">
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(event) =>
                      setRememberMe(
                        event.target.checked
                      )
                    }
                    disabled={isLoading}
                  />

                  <span className="nova-auth-checkbox-box">
                    <svg
                      viewBox="0 0 16 16"
                      focusable="false"
                    >
                      <path d="m3.2 8.2 3 3 6.6-6.7" />
                    </svg>
                  </span>

                  <span>
                    Remember me
                  </span>
                </label>
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
                    ? "AUTHENTICATING..."
                    : "SIGN IN"}
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
            Don't have an account?
          </span>

          <button
            type="button"
            onClick={handleCreateAccount}
            disabled={isLoading}
          >
            CREATE ACCOUNT
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