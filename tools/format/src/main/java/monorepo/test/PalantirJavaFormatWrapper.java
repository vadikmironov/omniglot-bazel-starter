package monorepo.test;

import com.palantir.javaformat.java.Main;

/**
 * Simple wrapper class for the Palantir Java formatter that defaults formatting
 * style to 120 characters line width and 4 spaces indent.
 */
public final class PalantirJavaFormatWrapper {
    private PalantirJavaFormatWrapper() {
    }

    private void run(String[] args) throws Exception {
        String[] modArgs = new String[args.length + 1];
        // please see the source code for the details:
        // https://github.com/palantir/palantir-java-format/blob/develop/palantir-java-format/src/main/java/com/palantir/javaformat/java/CommandLineOptionsParser.java
        modArgs[0] = "--palantir";
        System.arraycopy(args, 0, modArgs, 1, args.length);

        Main.main(modArgs);
    }

    public static void main(String[] args) {
        try {
            new PalantirJavaFormatWrapper().run(args);
        } catch (Exception ex) {
            ex.printStackTrace();
            System.exit(1);
        }
    }
}
