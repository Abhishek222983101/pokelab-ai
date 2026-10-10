//! `labd doctor` against the real binary — not a unit test of the checks in
//! isolation, but the actual CLI entrypoint a human runs before a demo.

#[test]
fn doctor_runs_and_env_key_check_reflects_reality() {
    let exe = env!("CARGO_BIN_EXE_labd");
    let core_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..") // crates/labd -> core
        .canonicalize()
        .unwrap();

    // without the secrets set, that specific check must fail and say so
    let out = std::process::Command::new(exe)
        .arg("doctor")
        .current_dir(&core_dir)
        .env_remove("LABD_BRAIN_SECRET")
        .env_remove("LABD_PAIRING_SECRET")
        .output()
        .unwrap();
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(stdout.contains("env_keys"));
    assert!(stdout.contains("missing: LABD_BRAIN_SECRET"));

    // with them set, that line must flip to a pass
    let out2 = std::process::Command::new(exe)
        .arg("doctor")
        .current_dir(&core_dir)
        .env("LABD_BRAIN_SECRET", "x")
        .env("LABD_PAIRING_SECRET", "y")
        .output()
        .unwrap();
    let stdout2 = String::from_utf8_lossy(&out2.stdout);
    assert!(stdout2.contains("✅ env_keys"));
}
