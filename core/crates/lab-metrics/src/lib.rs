//! lab-metrics: ring buffers and LTTB downsampling for live charts (§5.6).
//! LTTB (largest-triangle-three-buckets) keeps the *shape* of a curve (its
//! peaks, its elbow) when thinning tens of thousands of points down to the
//! ~50–600 a chart actually needs to draw.

use std::collections::VecDeque;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

/// Fixed-capacity ring buffer of (step, value) points for one (job, key).
#[derive(Debug, Clone)]
pub struct RingBuffer {
    capacity: usize,
    points: VecDeque<Point>,
}

impl RingBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            capacity,
            points: VecDeque::with_capacity(capacity.min(1024)),
        }
    }

    pub fn push(&mut self, x: f64, y: f64) {
        if self.points.len() == self.capacity {
            self.points.pop_front();
        }
        self.points.push_back(Point { x, y });
    }

    pub fn len(&self) -> usize {
        self.points.len()
    }

    pub fn is_empty(&self) -> bool {
        self.points.is_empty()
    }

    pub fn as_slice(&self) -> Vec<Point> {
        self.points.iter().copied().collect()
    }
}

/// Largest-Triangle-Three-Buckets downsampling to `threshold` points.
/// Always keeps the first and last point. `threshold < 3` returns the input
/// unchanged (nothing meaningful to downsample).
pub fn lttb(data: &[Point], threshold: usize) -> Vec<Point> {
    let n = data.len();
    if threshold >= n || threshold < 3 {
        return data.to_vec();
    }

    let mut sampled = Vec::with_capacity(threshold);
    sampled.push(data[0]);

    // bucket size for the (n - 2) interior points, split into threshold - 2 buckets
    let bucket_size = (n - 2) as f64 / (threshold - 2) as f64;
    let mut a = 0usize; // index of the previously selected point

    for i in 0..(threshold - 2) {
        let bucket_start = (i as f64 * bucket_size) as usize + 1;
        let bucket_end = ((i + 1) as f64 * bucket_size) as usize + 1;
        let bucket_end = bucket_end.min(n - 1);

        // average point of the NEXT bucket (used as one triangle vertex)
        let next_start = bucket_end;
        let next_end = (((i + 2) as f64 * bucket_size) as usize + 1).min(n);
        let next_end = next_end.max(next_start + 1).min(n);
        let (avg_x, avg_y) = avg_point(&data[next_start..next_end]);

        let point_a = data[a];
        let mut best_area = -1.0f64;
        let mut best_idx = bucket_start;
        // we need the index itself (it becomes `a` for the next bucket), so
        // iterating by index is clearer here than enumerate()+skip()+take().
        #[allow(clippy::needless_range_loop)]
        for j in bucket_start..bucket_end.max(bucket_start + 1) {
            let area = triangle_area(point_a, data[j], Point { x: avg_x, y: avg_y });
            if area > best_area {
                best_area = area;
                best_idx = j;
            }
        }
        sampled.push(data[best_idx]);
        a = best_idx;
    }

    sampled.push(data[n - 1]);
    sampled
}

fn avg_point(slice: &[Point]) -> (f64, f64) {
    if slice.is_empty() {
        return (0.0, 0.0);
    }
    let n = slice.len() as f64;
    let sx: f64 = slice.iter().map(|p| p.x).sum();
    let sy: f64 = slice.iter().map(|p| p.y).sum();
    (sx / n, sy / n)
}

fn triangle_area(a: Point, b: Point, c: Point) -> f64 {
    0.5 * ((a.x - c.x) * (b.y - a.y) - (a.x - b.x) * (c.y - a.y)).abs()
}
