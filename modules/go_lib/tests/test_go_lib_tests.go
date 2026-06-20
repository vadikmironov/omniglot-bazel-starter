package go_lib

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestDefaultLevelReturnsHelloWorld(t *testing.T) {
	assert.Equal(t, GetHelloWorldString(0), "Hello, World!")
	assert.Equal(t, GetHelloWorldString(3), "Hello, World!")
	assert.Equal(t, GetHelloWorldString(100), "Hello, World!")
}

func TestSpecificLevelReturnsHelloWorld(t *testing.T) {
	assert.Equal(t, GetHelloWorldString(1), "Hello, Star!")
	assert.Equal(t, GetHelloWorldString(2), "Hello, Superstar!")
	assert.Equal(t, GetHelloWorldString(3), "Hello, World!")
}
