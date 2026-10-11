import { describe, expect, it } from "vitest";
import { cleanPaperText } from "../panels";

describe("cleanPaperText", () => {
  it("repairs PDF small-caps splits and hyphenated line breaks", () => {
    expect(cleanPaperText("GROKKING : G ENERALIZATION BEYOND OVERFIT - TING")).toBe("GROKKING : GENERALIZATION BEYOND OVERFITTING");
    expect(cleanPaperText("on small al- gorithmically generated")).toBe("on small algorithmically generated");
  });
  it("cuts long chunks at a sentence end, never mid-word", () => {
    const long = "First sentence here is complete. " + "word ".repeat(120) + "tail without end";
    const out = cleanPaperText(long);
    expect(out.length).toBeLessThan(long.length);
    expect(out.endsWith(".") || out.endsWith("…")).toBe(true);
  });
});
