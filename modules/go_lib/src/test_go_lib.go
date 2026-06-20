package go_lib

var (
	hello_world_msg     = "Hello, World!"
	hello_star_msg      = "Hello, Star!"
	hello_superstar_msg = "Hello, Superstar!"
)

func GetHelloWorldString(level int) string {
	switch level {
	case 1:
		return hello_star_msg
	case 2:
		return hello_superstar_msg
	default:
		return hello_world_msg
	}
}
