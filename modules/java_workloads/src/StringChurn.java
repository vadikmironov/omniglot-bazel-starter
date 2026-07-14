package monorepo.workloads;

/**
 * O(n²) string concatenation: strings are immutable, so every round
 * allocates a fresh string and copies the whole accumulator — high
 * transient allocation rate, tiny live heap at any instant.
 */
public final class StringChurn {
    private StringChurn() {
    }

    public static String concat(int pieces, String piece) {
        String acc = "";
        for (int i = 0; i < pieces; i++) {
            // String.concat, not +: same fresh-allocation-and-copy churn,
            // without javac's invokedynamic concat rewriting it.
            acc = acc.concat(piece);
        }
        return acc;
    }
}
