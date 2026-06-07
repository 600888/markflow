import { createTheme } from "@mui/material/styles";

const SELECTED_BG = "#F3E8FF";
const TPL_SELECTED_BG = "#F3E8FF";

const light = createTheme({
  cssVariables: true,
  palette: {
    mode: "light",
    primary: { main: "#A855F7", light: SELECTED_BG },
    secondary: { main: "#EC4899" },
    success: { main: "#22C55E" },
    error: { main: "#EF4444" },
    background: { default: "#F7F8FA", paper: "#FFFFFF" },
    text: { primary: "#0A0A0A", secondary: "#71717A" },
    divider: "#E5E7EB",
  },
  typography: {
    fontFamily: `"Inter", "Funnel Sans", "Microsoft YaHei", sans-serif`,
    fontSize: 13,
  },
  shape: { borderRadius: 8 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: "none", fontWeight: 600 } } },
    MuiToggleButton: { styleOverrides: { root: { textTransform: "none" } } },
    MuiTab: { styleOverrides: { root: { textTransform: "none", minHeight: 44, fontSize: 12 } } },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiCssBaseline: { styleOverrides: { body: { background: "#E5E7EB" } } },
  },
});

const dark = createTheme({
  cssVariables: true,
  palette: {
    mode: "dark",
    primary: { main: "#A855F7", light: "#1e1b2e" },
    secondary: { main: "#EC4899" },
    success: { main: "#22C55E" },
    error: { main: "#EF4444" },
    background: { default: "#141414", paper: "#0A0A0A" },
    text: { primary: "#FFFFFF", secondary: "#A1A1AA" },
    divider: "#27272A",
  },
  typography: light.typography,
  shape: light.shape,
  components: light.components,
});

export { light, dark, SELECTED_BG, TPL_SELECTED_BG };
