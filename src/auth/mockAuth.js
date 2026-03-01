// ─────────────────────────────────────────────────────────────────────────────
// PLACEHOLDER AUTH MODULE — Singapore Children's Society YOUTHCARE
// ─────────────────────────────────────────────────────────────────────────────
//
// ⚠️  REAL-AUTH INTEGRATION POINTS:
//   Every function or comment tagged with // AUTH_SERVICE_CALL must be
//   replaced with an HTTP request to your actual auth service before
//   deploying to production.
//
//   Recommended endpoints to implement on your auth service:
//     POST /api/auth/login          { email, password }  → { user, access_token }
//     GET  /api/auth/me             Authorization: Bearer <token>  → UserObject
//     POST /api/auth/logout         Authorization: Bearer <token>
//     GET  /api/users               ?role=Youth+Helper  → UserObject[]
//
// ─────────────────────────────────────────────────────────────────────────────

const CASE_SERVICE_URL = "http://localhost:8001";

// ── Fetch all users from MongoDB ──────────────────────────────────────────────
// AUTH_SERVICE_CALL: Replace with GET /api/users from your auth service
let cachedUsers = null;

async function fetchUsersFromDB() {
  if (cachedUsers) return cachedUsers;
  
  try {
    const response = await fetch(`${CASE_SERVICE_URL}/users`);
    if (!response.ok) {
      throw new Error(`Failed to fetch users: ${response.status}`);
    }
    cachedUsers = await response.json();
    return cachedUsers;
  } catch (error) {
    console.error("Error fetching users from MongoDB:", error);
    return [];
  }
}

// ── AUTH_SERVICE_CALL ─────────────────────────────────────────────────────────
// Replace this function with:
//   const res = await fetch("/api/auth/login", {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({ email, password }),
//   });
//   if (!res.ok) throw new Error(await res.text());
//   return res.json(); // { user, access_token }
export async function mockLogin(email, password) {
  await new Promise(r => setTimeout(r, 650)); // simulate network round-trip
  
  const users = await fetchUsersFromDB();
  const user = users.find(u => u.email.toLowerCase() === email.trim().toLowerCase());
  
  if (!user) throw new Error("No account found with that email address.");
  
  // For dev: accept "admin123" for admins, "helper123" for helpers
  const expectedPassword = user.role === "admin" ? "admin123" : "helper123";
  if (password !== expectedPassword) {
    throw new Error("Incorrect password. Please try again.");
  }
  
  const token = `mock-jwt-${user.user_id}-${Date.now()}`;
  return { user, token };
}

// ── AUTH_SERVICE_CALL ─────────────────────────────────────────────────────────
// Replace with: GET /api/auth/me  (Authorization: Bearer <stored_token>)
export async function mockGetCurrentUser(token) {
  if (!token || !token.startsWith("mock-jwt-")) return null;
  
  const parts = token.split("-");
  const userId = parts[2];
  
  const users = await fetchUsersFromDB();
  const user = users.find(u => u.user_id === userId);
  
  return user || null;
}

// ── AUTH_SERVICE_CALL ─────────────────────────────────────────────────────────
// Replace with: POST /api/auth/logout  (Authorization: Bearer <token>)
export async function mockLogout() {
  await new Promise(r => setTimeout(r, 150));
  cachedUsers = null; // Clear cache on logout
  // In production: revoke the server-side session / JWT refresh token here.
}

// ── Helpers for UI components ─────────────────────────────────────────────────
export async function getHelperUsers() {
  const users = await fetchUsersFromDB();
  return users.filter(u => u.role === "youth_helper");
}

export async function getAllUsers() {
  return await fetchUsersFromDB();
}

// Quick-access demo credential table (shown on login page for evaluators)
// Note: Now references MongoDB users
export const DEMO_CREDENTIALS = [
  { role: "Admin",        email: "sarah.admin@example.com", password: "admin123",  name: "Admin Sarah" },
  { role: "Admin",        email: "mike.admin@example.com",  password: "admin123",  name: "Admin Mike"  },
  { role: "Youth Helper", email: "alex.johnson@example.com", password: "helper123", name: "Alex Johnson" },
  { role: "Youth Helper", email: "maya.patel@example.com",   password: "helper123", name: "Maya Patel"   },
  { role: "Youth Helper", email: "jordan.lee@example.com",   password: "helper123", name: "Jordan Lee"   },
];
