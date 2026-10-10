fn main() {
    println!("{:#?}", lab_telemetry::sample_gpu());
    let p = lab_telemetry::sample_power();
    println!("{:#?}", p);
    println!("should_warn_power: {}", lab_telemetry::should_warn_power(&p));
}
