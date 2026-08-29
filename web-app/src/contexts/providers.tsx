// custom content providers in one file for easier management and to avoid circular dependencies
import { AuthProvider } from "./AuthContext";
import { ThemeContextProvider } from "./ThemeContext";
import { CurrencyProvider } from "./CurrencyContext";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ThemeContextProvider>
        <CurrencyProvider>
          <AuthProvider>{children}</AuthProvider>
        </CurrencyProvider>
      </ThemeContextProvider>
    </>
  );
}
