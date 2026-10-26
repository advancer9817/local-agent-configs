package main

import (
	"path/filepath"
	"runtime"

	webview2 "github.com/jchv/go-webview2"
	"github.com/jchv/go-webview2/webviewloader"
)

func launchDesktop(address, root string, closing <-chan struct{}) bool {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	if version, err := webviewloader.GetInstalledVersion(); err != nil || version == "" {
		return false
	}
	w := webview2.NewWithOptions(webview2.WebViewOptions{
		Debug: false, AutoFocus: true,
		DataPath: filepath.Join(root, "webview"),
		WindowOptions: webview2.WindowOptions{
			Title: "Hindsight · 初始化与接入", Width: 1180, Height: 850, Center: true,
		},
	})
	if w == nil {
		// Machines without the WebView2 runtime still have a working browser mode.
		return false
	}
	defer w.Destroy()
	w.SetSize(840, 620, webview2.HintMin)
	w.Navigate(address)
	done := make(chan struct{})
	defer close(done)
	go func() {
		select {
		case <-closing:
			w.Dispatch(func() { w.Terminate() })
		case <-done:
		}
	}()
	w.Run()
	return true
}
