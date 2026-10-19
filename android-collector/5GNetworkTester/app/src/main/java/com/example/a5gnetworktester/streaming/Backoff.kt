package com.example.a5gnetworktester.streaming

/**
 * Clock abstraction for deterministic time testing (T12-004).
 */
interface Clock {
    fun currentTimeMillis(): Long
}

object SystemClock : Clock {
    override fun currentTimeMillis(): Long = System.currentTimeMillis()
}

/**
 * Fake clock for unit testing backoff and timers without thread sleeping.
 */
class FakeClock(private var currentTime: Long = 0L) : Clock {
    override fun currentTimeMillis(): Long = currentTime

    fun advanceBy(millis: Long) {
        currentTime += millis
    }

    fun setTime(millis: Long) {
        currentTime = millis
    }
}

/**
 * Exponential backoff with jitter and 30-second cap (T12-004).
 *
 * Implements exponential increase: initialDelayMs * (factor ^ attempt),
 * bounded by maxDelayMs (default 30,000 ms = 30 s), with randomized jitter.
 */
class ExponentialBackoff(
    val initialDelayMs: Long = 1000L,
    val maxDelayMs: Long = 30000L,
    val factor: Double = 2.0,
    val jitterFactor: Double = 0.25,
    private val randomProvider: () -> Double = { Math.random() },
    val clock: Clock = SystemClock
) {
    var attempt: Int = 0
        private set

    /**
     * Computes the next backoff delay in milliseconds.
     * Capped strictly at maxDelayMs (30 s).
     */
    fun nextDelayMs(): Long {
        val baseDelay = (initialDelayMs * Math.pow(factor, attempt.toDouble())).toLong()
        val cappedBase = baseDelay.coerceAtMost(maxDelayMs)
        attempt++

        // Symmetric jitter: [1 - jitterFactor, 1 + jitterFactor]
        val jitter = (1.0 - jitterFactor) + (2.0 * jitterFactor * randomProvider())
        val delay = (cappedBase * jitter).toLong()

        return delay.coerceIn(0L, maxDelayMs)
    }

    /**
     * Resets backoff attempt counter after successful connection.
     */
    fun reset() {
        attempt = 0
    }
}
