# Frontend upgrade checks

## Completed locally

- `npm install` installs local QR generation (`qrcode` 1.5.4; `@types/qrcode` 1.5.5). Lockfile included.
- `npm run build` compiles TypeScript and builds with Vite.
- `npm audit --json` reports zero vulnerabilities after upgrading the existing Vite 6.3.5 to 6.4.5 (same major version).
- Browser smoke check at local port 5174: login screen renders; visiting `/#ticket=local-smoke-test-only` removes the fragment immediately and shows the administrator sign-in requirement. No checkout request is made from consuming a fragment.
- Local QR encoder smoke check: same-site-shaped URL with opaque token generates a PNG data URL without using an external QR service.

## Integration checks still needed with the upgraded backend

1. Login/register and allocation: retry a failed allocation unchanged and verify the same request key is used; changing the vehicle creates a new key.
2. Check available/occupied/closed counts, own-space highlight, zone and row labels. Compare slot labels against backend data (not fabricated P-id labels).
3. Observe `/slots` polling every five seconds, with only one slot request in flight. Hide the tab (polls stop), return/focus/reconnect (immediate refresh), interrupt the connection (retry backoff and stale status), then log out during an in-flight request (no session revival).
4. Administrator: add/edit a space, close/reopen it, attempt an obsolete version update and check the conflict message. Closed occupied spaces must not be checked out by closing.
5. Generate and refresh an own-booking QR. Decode it and confirm URL contains only same-site path plus opaque `#ticket=` token (no vehicle, booking identifier or auth JWT). Print preview must contain only the ticket and QR.
6. Open a QR link logged out. Sign in as a regular user (admin action unavailable), then an administrator. Preview does not check out. Explicit confirmation calls checkout and displays completion/final amount. Expired/invalid tokens show server errors.
7. Checkout through the normal own-booking action, then refresh account/history; QR disappears and the final amount is visible. No payment is actually collected.
8. Inspect mobile widths 320/480/760 px and keyboard-only use; verify forms, state text, table scrolling, and print output.

There is no camera scanner implementation: the accessible paste-token/QR-link fallback is explicitly labeled. Account/history/admin data refresh on sign-in and explicit actions, not a second automatic polling loop. Layout is illustrative and not a surveyed map. Backend authentication, ticket hashing/expiry/rotation and concurrent billing correctness remain backend responsibilities.
