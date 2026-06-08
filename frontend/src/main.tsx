import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { useStore } from "./stores/useStore";
import App from "./App";
import "./index.css";

function ThemeManager() {
  const theme = useStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }, [theme]);

  return null;
}

function Root() {
  return (
    <>
      <ThemeManager />
      <App />
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
