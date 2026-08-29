import { useMutation } from "@tanstack/react-query";
import {
  authService,
  ChangePasswordPayload,
  EmailVerifyConfirmPayload,
  EmailVerifyRequestPayload,
  LoginPayload,
  PasswordResetPayload,
  PinLoginPayload,
  PinSetupConfirmPayload,
  PinSetupRequestPayload,
  RefreshTokenPayload,
  RegisterPayload,
  RequestPasswordResetPayload,
} from "@/services/auth";

export const useRegister = () => {
  return useMutation({
    mutationFn: (data: RegisterPayload) => authService.register(data),
    onSuccess: () => {
      // Handle successful Register
      // if (data) {
      //   localStorage.setItem("accessToken", data.accessToken);
      // }
    },
  });
};

export const useLogin = () => {
  // Tokens are stored once by AuthContext.login(). Nothing is logged to the
  // console here so access/refresh tokens never leak into browser devtools.
  return useMutation({
    mutationFn: (data: LoginPayload) => authService.login(data),
  });
};

export const useEmailVerifyRequest = () => {
  return useMutation({
    mutationFn: (data: EmailVerifyRequestPayload) =>
      authService.emailVerifyRequest(data),
  });
};

export const useEmailVerify = () => {
  return useMutation({
    mutationFn: (data: EmailVerifyConfirmPayload) => authService.emailVerify(data),
  });
};

export const useRequestPasswordReset = () => {
  return useMutation({
    mutationFn: (data: RequestPasswordResetPayload) =>
      authService.requestPasswordReset(data),
    onSuccess: (data) => {
      return data;
    },
  });
};

export const usePasswordReset = () => {
  return useMutation({
    mutationFn: (data: PasswordResetPayload) => authService.passwordReset(data),
    onSuccess: (data) => {
      return data;
    },
  });
};

export const useChangePassword = () => {
  return useMutation({
    mutationFn: (data: ChangePasswordPayload) => authService.changePassword(data),
  });
};

export const usePinSetupRequest = () => {
  return useMutation({
    mutationFn: (data: PinSetupRequestPayload) =>
      authService.pinSetupRequest(data),
  });
};

export const usePinSetupConfirm = () => {
  return useMutation({
    mutationFn: (data: PinSetupConfirmPayload) =>
      authService.pinSetupConfirm(data),
  });
};

export const usePinLogin = () => {
  return useMutation({
    mutationFn: (data: PinLoginPayload) => authService.pinLogin(data),
  });
};

export const useLogout = () => {
  return useMutation({
    mutationFn: () => authService.logout(),
    onSuccess: (data) => {
      localStorage.removeItem("accessToken");
      localStorage.removeItem("refreshToken");
      return data;
    },
  });
};

export const useRefreshToken = () => {
  return useMutation({
    mutationFn: (data: RefreshTokenPayload) => authService.refreshToken(data),
    onSuccess: () => {
      // localStorage.setItem("refreshToken", data.refresh || "");
    },
  });
};
