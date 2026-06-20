extern crate rust_lib;

// not required for tests, but for test library builds this line would emit
// unused import warning and test gate effectively suppresses it
#[cfg(test)]
use rust_lib::hello_world_lib_impl::HelloWorldLib;

#[test]
fn test_hello_world_lib() {
    assert_eq!(HelloWorldLib.get_hello_world_string(None), "Hello, World!");
    assert_eq!(
        HelloWorldLib.get_hello_world_string(Some(0)),
        "Hello, World!"
    );
    assert_eq!(
        HelloWorldLib.get_hello_world_string(Some(1)),
        "Hello, Star!"
    );
    assert_eq!(
        HelloWorldLib.get_hello_world_string(Some(2)),
        "Hello, Superstar!"
    );
}
