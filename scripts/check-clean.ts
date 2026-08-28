/**
 * Refuse to publish anything that looks like private data.
 *
 * This exists because "remember not to commit your real config" is not a
 * safeguard, it is a wish. The check runs over files git actually TRACKS --
 * the ones that would be published -- rather than the working tree, because an
 * ignored file sitting on disk is exactly the situation this is protecting.
 *
 *   npm run check-clean
 *
 * Exits non-zero on a finding, so it works as a pre-commit hook or a CI step.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, statSync } from "node:fs";

interface Finding {
  file: string;
  line: number;
  rule: string;
  detail: string;
}

/** Files that must never be tracked, however tempting. */
const FORBIDDEN_PATHS: { pattern: RegExp; why: string }[] = [
  { pattern: /^\.env$|^\.env\.(?!example)/, why: "environment file with secrets" },
  { pattern: /^\.auth\//, why: "saved browser session (login cookies)" },
  { pattern: /^output\//, why: "run output, may contain booking data" },
  { pattern: /^input\//, why: "imported data, may contain guest data" },
  // config/*.json is a real property's setup; only the examples are shareable.
  { pattern: /^config\/(?!.*\.example\.json$).*\.json$/, why: "real configuration" },
];

/**
 * Content patterns. Each must be specific enough not to fire constantly --
 * a check that cries wolf gets bypassed, which is worse than no check.
 */
const CONTENT_RULES: { rule: string; pattern: RegExp; allow?: RegExp }[] = [
  {
    rule: "database connection string",
    pattern: /\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/[^\s"'`]+/gi,
    // The example file documents the shape; placeholder credentials are fine.
    allow: /user:password@|USER:PASSWORD@|<[^>]+>/,
  },
  {
    rule: "private key",
    pattern: /-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----/g,
  },
  {
    rule: "API token",
    pattern: /\b(?:ghp|gho|ghs|github_pat|sk-|xox[baprs]-|AKIA)[A-Za-z0-9_-]{16,}\b/g,
  },
  {
    rule: "possible room or property id",
    // A bare 8+ digit run. Real extranet room ids look like this; so do very
    // few legitimate things in source code.
    pattern: /(?<![\w.-])\d{8,}(?![\w.-])/g,
    // Obvious placeholders and timestamps are fine.
    allow: /^0+$|^(?:1234567890|9{8,})$|^1[0-9]{12}$/,
  },
  {
    rule: "email address",
    pattern: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
    allow: /example\.(?:com|org|net)$|@your-|noreply@/i,
  },
];

const SKIP_FILES = /(?:^|\/)(?:package-lock\.json|LICENSE)$|\.(?:png|jpe?g|gif|webp|ico|pdf|zip)$/i;

function trackedFiles(): string[] {
  return execFileSync("git", ["ls-files"], { encoding: "utf-8" }).split("\n").filter(Boolean);
}

function scan(): Finding[] {
  const findings: Finding[] = [];

  for (const file of trackedFiles()) {
    for (const { pattern, why } of FORBIDDEN_PATHS) {
      if (pattern.test(file)) {
        findings.push({ file, line: 0, rule: "forbidden path", detail: why });
      }
    }
    if (SKIP_FILES.test(file)) continue;

    let text: string;
    try {
      if (statSync(file).size > 2_000_000) continue;
      text = readFileSync(file, "utf-8");
    } catch {
      continue; // binary or unreadable; the path rules already covered it
    }
    // This file necessarily contains the patterns it searches for.
    if (file === "scripts/check-clean.ts") continue;

    text.split("\n").forEach((lineText, index) => {
      for (const { rule, pattern, allow } of CONTENT_RULES) {
        for (const match of lineText.match(pattern) ?? []) {
          if (allow?.test(match)) continue;
          findings.push({ file, line: index + 1, rule, detail: match.slice(0, 60) });
        }
      }
    });
  }
  return findings;
}

const findings = scan();
if (findings.length === 0) {
  console.log(`Clean: ${trackedFiles().length} tracked file(s), nothing private found.`);
} else {
  console.error(`${findings.length} problem(s) — do not publish until these are resolved:\n`);
  for (const finding of findings) {
    const where = finding.line > 0 ? `${finding.file}:${finding.line}` : finding.file;
    console.error(`  ${where}\n    ${finding.rule}: ${finding.detail}`);
  }
  console.error(
    `\nIf a finding is a false positive, adjust the rule in scripts/check-clean.ts ` +
      `and say why in the commit.`
  );
  process.exitCode = 1;
}
