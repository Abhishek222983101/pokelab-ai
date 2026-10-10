//! The event hub: every event that is ever shown anywhere passes through
//! `Hub::publish`, which appends it to the durable store and then
//! broadcasts it to every live subscriber (WS clients, the brain socket).
//! This is what makes "the event log is the trace" true — there is no
//! other path to the screen (§5.4.2, §11.5).

use std::sync::Arc;

use lab_store::{Event, NewEvent, Store};
use tokio::sync::broadcast;

/// Bounded per spec (§5.4.2): a slow subscriber gets `resync` and drops its
/// backlog rather than ever blocking the publisher side.
pub const EVENT_QUEUE_CAPACITY: usize = 4096;

#[derive(Clone)]
pub struct Hub {
    store: Arc<Store>,
    tx: broadcast::Sender<Event>,
}

impl Hub {
    pub fn new(store: Arc<Store>) -> Self {
        let (tx, _rx) = broadcast::channel(EVENT_QUEUE_CAPACITY);
        Self { store, tx }
    }

    /// Append + broadcast, atomically from the caller's point of view: a
    /// subscriber that is live before this call either sees the event via
    /// the broadcast or (if it subscribed after) via a `since` replay — the
    /// store write happens first, so replay can never show a seq the
    /// broadcast hasn't been told about yet.
    pub fn publish(&self, event: NewEvent) -> lab_store::Result<Event> {
        let committed = self.store.append(event)?;
        // a send error just means "nobody is listening right now" — fine
        let _ = self.tx.send(committed.clone());
        Ok(committed)
    }

    pub fn subscribe(&self) -> broadcast::Receiver<Event> {
        self.tx.subscribe()
    }

    pub fn store(&self) -> &Arc<Store> {
        &self.store
    }
}
