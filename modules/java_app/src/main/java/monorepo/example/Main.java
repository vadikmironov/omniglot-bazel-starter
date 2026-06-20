package monorepo.example;

public final class Main {

    private Main() {
    }

    public static void main(String[] args) {
        System.out.println(">> using java " + Runtime.version().toString());
        System.out.println(">> located at " + System.getProperties().getProperty("java.home"));

        System.out.println(HelloWorldLibrary.getHelloWorldString(3));
    }
}
