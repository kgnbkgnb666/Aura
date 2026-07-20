export const AURA_GITHUB_URL = "https://github.com/kgnbkgnb666/Aura";
const LATEST_RELEASE_URL = "https://api.github.com/repos/kgnbkgnb666/Aura/releases/latest";

export type UpdateCheckResult = {
  currentVersion: string;
  latestVersion: string;
  releaseUrl: string;
  hasUpdate: boolean;
  published: boolean;
};

function versionParts(value: string): number[] {
  return value.replace(/^v/i, "").split(".").map((part) => Number.parseInt(part, 10) || 0);
}

function isNewerVersion(candidate: string, current: string): boolean {
  const candidateParts = versionParts(candidate);
  const currentParts = versionParts(current);
  const length = Math.max(candidateParts.length, currentParts.length);
  for (let index = 0; index < length; index += 1) {
    const left = candidateParts[index] || 0;
    const right = currentParts[index] || 0;
    if (left !== right) return left > right;
  }
  return false;
}

export async function checkGitHubUpdate(currentVersion: string): Promise<UpdateCheckResult> {
  const response = await fetch(LATEST_RELEASE_URL, {
    headers: { Accept: "application/vnd.github+json" }
  });
  if (response.status === 404) {
    return {
      currentVersion,
      latestVersion: currentVersion,
      releaseUrl: `${AURA_GITHUB_URL}/releases`,
      hasUpdate: false,
      published: false
    };
  }
  if (!response.ok) throw new Error(`GitHub update check failed: ${response.status}`);
  const release = await response.json() as { tag_name?: string; html_url?: string };
  const latestVersion = String(release.tag_name || "").replace(/^v/i, "");
  if (!latestVersion) throw new Error("GitHub release does not include a version tag");
  return {
    currentVersion,
    latestVersion,
    releaseUrl: release.html_url || `${AURA_GITHUB_URL}/releases/latest`,
    hasUpdate: isNewerVersion(latestVersion, currentVersion),
    published: true
  };
}
