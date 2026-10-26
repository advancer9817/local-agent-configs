//go:build !windows

package main

func protect(value string) (string, error)   { return value, nil }
func unprotect(value string) (string, error) { return value, nil }
