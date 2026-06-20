package monorepo.example;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

public class HelloWorldLibraryTest {

    @Test
    public void testDefault() {
        assertEquals("Hello, World!", HelloWorldLibrary.getHelloWorldString(0));
    }

    @Test
    public void testLevelOne() {
        assertEquals("Hello, Star!", HelloWorldLibrary.getHelloWorldString(1));
    }

    @Test
    public void testLevelTwo() {
        assertEquals("Hello, Superstar!", HelloWorldLibrary.getHelloWorldString(2));
    }
}
