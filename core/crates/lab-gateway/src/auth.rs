//! Auth & pairing (§5.8). Desk (localhost) gets full control; phone pairs
//! via a short-lived single-use code and gets an HMAC-signed token; a
//! `view` role is read-only. Pairing codes are meant to travel in a URL
//! **fragment**, which browsers never send to a server — that part is the
//! frontend's job; this module only issues/claims/verifies.

use std::collections::HashMap;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use hmac::{Hmac, Mac};
use rand::Rng;
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Role {
    Desk,
    Phone,
    View,
}

impl Role {
    pub fn as_str(&self) -> &'static str {
        match self {
            Role::Desk => "desk",
            Role::Phone => "phone",
            Role::View => "view",
        }
    }

    pub fn parse(s: &str) -> Option<Self> {
        match s {
            "desk" => Some(Role::Desk),
            "phone" => Some(Role::Phone),
            "view" => Some(Role::View),
            _ => None,
        }
    }

    /// §5.4.4 role rules.
    pub fn can(&self, command: &str) -> bool {
        match self {
            Role::Desk => true,
            Role::Phone => matches!(
                command,
                "approve" | "reject" | "redirect" | "kill_job" | "feedback" | "ask"
            ),
            Role::View => false,
        }
    }
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

struct PendingCode {
    role: Role,
    expires_at: u64,
}

/// In-memory single-use pairing codes, 5-minute TTL (§5.8).
pub struct PairingStore {
    codes: Mutex<HashMap<String, PendingCode>>,
}

impl Default for PairingStore {
    fn default() -> Self {
        Self::new()
    }
}

impl PairingStore {
    pub fn new() -> Self {
        Self {
            codes: Mutex::new(HashMap::new()),
        }
    }

    /// 6 uppercase alphanumeric chars, excluding visually ambiguous ones.
    pub fn issue(&self, role: Role) -> String {
        const ALPHABET: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        let mut rng = rand::thread_rng();
        let code: String = (0..6)
            .map(|_| ALPHABET[rng.gen_range(0..ALPHABET.len())] as char)
            .collect();
        self.codes.lock().unwrap().insert(
            code.clone(),
            PendingCode {
                role,
                expires_at: now_secs() + 5 * 60,
            },
        );
        code
    }

    /// Consumes the code if valid and unexpired; returns None otherwise
    /// (wrong code, already used, or expired).
    pub fn claim(&self, code: &str) -> Option<Role> {
        let mut map = self.codes.lock().unwrap();
        let entry = map.remove(code)?;
        if entry.expires_at < now_secs() {
            None
        } else {
            Some(entry.role)
        }
    }
}

/// Issues `HMAC(secret, device_id|role|expiry)` as a token string
/// `device_id|role|expiry|hex(mac)`, valid for `ttl_hours` (24h default).
pub fn issue_token(secret: &[u8], device_id: &str, role: Role, ttl_hours: u64) -> String {
    let expiry = now_secs() + ttl_hours * 3600;
    let payload = format!("{device_id}|{}|{expiry}", role.as_str());
    let mut mac = HmacSha256::new_from_slice(secret).expect("HMAC accepts any key length");
    mac.update(payload.as_bytes());
    let sig = hex::encode(mac.finalize().into_bytes());
    format!("{payload}|{sig}")
}

/// Verifies a token's signature and expiry; returns (device_id, role).
pub fn verify_token(secret: &[u8], token: &str) -> Option<(String, Role)> {
    let (payload, sig_hex) = token.rsplit_once('|')?;

    let mut mac = HmacSha256::new_from_slice(secret).ok()?;
    mac.update(payload.as_bytes());
    let expected = hex::encode(mac.finalize().into_bytes());
    if expected != sig_hex {
        return None;
    }

    let mut fields = payload.split('|');
    let device_id = fields.next()?.to_string();
    let role = Role::parse(fields.next()?)?;
    let expiry: u64 = fields.next()?.parse().ok()?;
    if expiry < now_secs() {
        return None;
    }
    Some((device_id, role))
}
