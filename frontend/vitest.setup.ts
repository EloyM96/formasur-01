import "@testing-library/jest-dom";
import { vi } from "vitest";

// Minimal mock para Link de Next.js durante las pruebas de Vitest.
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: any) => (
    <a href={href as string} {...props}>
      {children}
    </a>
  ),
}));
