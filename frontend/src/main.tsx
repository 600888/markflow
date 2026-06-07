import { StrictMode, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { useStore } from "./stores/useStore";
import { light, dark } from "./theme";
import App from "./App";

function Root() {
  const themeMode = useStore((s) => s.theme);
  const theme = useMemo(() => (themeMode === "dark" ? dark : light), [themeMode]);
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
