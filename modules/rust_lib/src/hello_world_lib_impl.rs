const HELLO_WORLD_SLICE: &str = "Hello, World!";
const HELLO_STAR_SLICE: &str = "Hello, Star!";
const HELLO_SUPERSTAR_SLICE: &str = "Hello, Superstar!";

pub struct HelloWorldLib;

impl HelloWorldLib {
    pub fn get_hello_world_string(&self, level: Option<u32>) -> &str {
        match level.unwrap_or(0) {
            1 => HELLO_STAR_SLICE,
            2 => HELLO_SUPERSTAR_SLICE,
            _ => HELLO_WORLD_SLICE,
        }
    }
}
