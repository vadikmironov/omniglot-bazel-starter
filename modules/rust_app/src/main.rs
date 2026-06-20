extern crate rust_lib;

use rust_lib::hello_world_lib_impl;

fn main() {
    let s = hello_world_lib_impl::HelloWorldLib.get_hello_world_string(None);
    println!("{s}");
}
