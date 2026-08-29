import api from "../lib/api";

export interface RegisterPayload {
  first_name: string;
  last_name: string;
  phone_number: string;
  email: string;
  password: string;
  confirm_password: string;
}

export interface RegisterMemberInfo {
  membership_number: string;
  is_verified: boolean;
  phone_verified: boolean;
  status: string;
}

export interface RegisterResponse {
  username: string;
  role: string;
  email: string;
  member: RegisterMemberInfo | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}
export interface RefreshTokenPayload {
  refresh: string;
}

export interface RequestPasswordResetPayload {
  email: string;
}

export interface PasswordResetPayload {
  token: string;
  uid: string;
  password: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

export interface GenericResponse {
  message?: string;
  success?: boolean;
}

export interface AuthResponse {
  access: string;
  refresh?: string;
}

export interface EmailVerifyRequestPayload {
  email: string;
}

export interface EmailVerifyConfirmPayload {
  email: string;
  code: string;
}

export interface EmailVerifyResponse {
  message?: string;
  already_verified?: boolean;
  dev_code?: string;
  expires_in_minutes?: number;
  email_sent?: boolean;
  email_error?: string;
}

export interface EmailVerifyConfirmResponse {
  message?: string;
  already_verified?: boolean;
}

export interface PinSetupRequestPayload {
  phone_number: string;
}

export interface PinSetupConfirmPayload {
  phone_number: string;
  code: string;
  pin: string;
}

export interface PinSetupResponse {
  message?: string;
  success?: boolean;
  already_set?: boolean;
  expires_in_minutes?: number;
  email_sent?: boolean;
  email_error?: string;
  dev_code?: string;
}

export interface PinLoginPayload {
  phone_number: string;
  pin: string;
}

export interface PinLoginResponse extends AuthResponse {
  detail?: string;
  email_not_verified?: boolean;
  pin_not_set?: boolean;
  pin_locked?: boolean;
  pin_invalid?: boolean;
  locked_seconds?: number;
}

export const authService = {
  register: (data: RegisterPayload) =>
    api.post("/auth/register", data) as Promise<RegisterResponse>,

  login: (data: LoginPayload) =>
    api.post("/auth/login", data) as Promise<AuthResponse>,

  logout: () => api.post("/auth/logout") as Promise<GenericResponse>,

  pinSetupRequest: (data: PinSetupRequestPayload) =>
    api.post("/auth/pin/setup-request", data) as Promise<PinSetupResponse>,

  pinSetupConfirm: (data: PinSetupConfirmPayload) =>
    api.post("/auth/pin/setup-confirm", data) as Promise<PinSetupResponse>,

  pinLogin: (data: PinLoginPayload) =>
    api.post("/auth/pin/login", data) as Promise<PinLoginResponse>,

  refreshToken: (data: RefreshTokenPayload) =>
    api.post("/auth/refresh-token", data) as Promise<AuthResponse>,

  emailVerifyRequest: (data: EmailVerifyRequestPayload) =>
    api.post("/auth/email-verify-request", data) as Promise<EmailVerifyResponse>,

  emailVerify: (data: EmailVerifyConfirmPayload) =>
    api.post("/auth/email-verify", data) as Promise<EmailVerifyConfirmResponse>,

  requestPasswordReset: (data: RequestPasswordResetPayload) =>
    api.post("/auth/request-password-reset", data) as Promise<GenericResponse>,

  passwordReset: (data: PasswordResetPayload) =>
    api.post("/auth/password-reset", data) as Promise<GenericResponse>,

  changePassword: (data: ChangePasswordPayload) =>
    api.post("/auth/change-password", data) as Promise<GenericResponse>,
};
