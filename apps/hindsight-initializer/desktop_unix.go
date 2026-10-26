//go:build !windows

package main

func launchDesktop(address, root string, closing <-chan struct{}) bool { return false }
