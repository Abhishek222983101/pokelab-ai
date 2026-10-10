use lab_metrics::{lttb, Point, RingBuffer};

fn pt(x: f64, y: f64) -> Point {
    Point { x, y }
}

#[test]
fn lttb_keeps_first_and_last() {
    let data: Vec<Point> = (0..1000).map(|i| pt(i as f64, (i as f64).sin())).collect();
    let out = lttb(&data, 50);
    assert_eq!(out.len(), 50);
    assert_eq!(out[0], data[0]);
    assert_eq!(out[out.len() - 1], data[data.len() - 1]);
}

#[test]
fn lttb_passthrough_when_threshold_too_small_or_too_large() {
    let data: Vec<Point> = (0..10).map(|i| pt(i as f64, i as f64)).collect();
    assert_eq!(lttb(&data, 2).len(), data.len()); // threshold < 3 -> unchanged
    assert_eq!(lttb(&data, 1000).len(), data.len()); // threshold >= n -> unchanged
}

#[test]
fn lttb_preserves_a_sharp_spike() {
    // a flat line with one spike in the middle — a naive stride-based
    // downsample would likely miss it; LTTB should keep it because it
    // maximizes the triangle area, which the spike dominates.
    let mut data: Vec<Point> = (0..500).map(|i| pt(i as f64, 0.0)).collect();
    data[250].y = 100.0;
    let out = lttb(&data, 50);
    let max_y = out.iter().map(|p| p.y).fold(f64::MIN, f64::max);
    assert_eq!(max_y, 100.0, "the spike must survive downsampling");
}

#[test]
fn ring_buffer_evicts_oldest_at_capacity() {
    let mut rb = RingBuffer::new(3);
    for i in 0..5 {
        rb.push(i as f64, i as f64);
    }
    assert_eq!(rb.len(), 3);
    let pts = rb.as_slice();
    assert_eq!(pts[0].x, 2.0);
    assert_eq!(pts[2].x, 4.0);
}
