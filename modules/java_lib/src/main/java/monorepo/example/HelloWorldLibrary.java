package monorepo.example;

public final class HelloWorldLibrary {

    private HelloWorldLibrary() {
    }

    public static String getHelloWorldString(int level) {
        return switch (level) {
            case 1 ->
                "Hello, Star!";
            case 2 ->
                "Hello, Superstar!";
            default ->
                "Hello, World!";
        };
    }
}
