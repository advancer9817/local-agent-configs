package main

import (
	"encoding/base64"
	"fmt"
	"strings"
	"syscall"
	"unsafe"
)

type dataBlob struct {
	Size uint32
	Data *byte
}

var (
	crypt32  = syscall.NewLazyDLL("crypt32.dll")
	kernel32 = syscall.NewLazyDLL("kernel32.dll")
)

func crypt(value []byte, decrypt bool) ([]byte, error) {
	in := dataBlob{Size: uint32(len(value))}
	if len(value) > 0 {
		in.Data = &value[0]
	}
	var out dataBlob
	name := "CryptProtectData"
	if decrypt {
		name = "CryptUnprotectData"
	}
	ok, _, err := crypt32.NewProc(name).Call(
		uintptr(unsafe.Pointer(&in)), 0, 0, 0, 0, 1, uintptr(unsafe.Pointer(&out)),
	)
	if ok == 0 {
		return nil, fmt.Errorf("Windows 凭据保护失败：%w", err)
	}
	defer kernel32.NewProc("LocalFree").Call(uintptr(unsafe.Pointer(out.Data)))
	return append([]byte(nil), unsafe.Slice(out.Data, int(out.Size))...), nil
}

func protect(value string) (string, error) {
	if value == "" {
		return "", nil
	}
	b, err := crypt([]byte(value), false)
	return "dpapi:" + base64.StdEncoding.EncodeToString(b), err
}

func unprotect(value string) (string, error) {
	if !strings.HasPrefix(value, "dpapi:") {
		return value, nil
	}
	b, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(value, "dpapi:"))
	if err != nil {
		return "", err
	}
	b, err = crypt(b, true)
	return string(b), err
}
