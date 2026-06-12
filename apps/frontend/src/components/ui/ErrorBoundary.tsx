import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100vh",
              gap: 16,
              color: "var(--color-muted)",
              fontSize: 14,
            }}
          >
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--color-ink)" }}>
              页面加载出错
            </div>
            <button
              type="button"
              onClick={() => this.setState({ hasError: false })}
              style={{
                padding: "8px 20px",
                borderRadius: 10,
                border: "none",
                background: "var(--color-ink)",
                color: "white",
                cursor: "pointer",
                fontSize: 14,
                fontWeight: 600,
              }}
            >
              重试
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
