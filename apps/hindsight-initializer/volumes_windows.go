//go:build windows

package main

import (
	"fmt"

	"golang.org/x/sys/windows"
)

func documentVolumes() []DocumentVolume {
	volumes := []DocumentVolume{}
	mask, err := windows.GetLogicalDrives()
	if err != nil {
		return volumes
	}
	for i := 0; i < 26; i++ {
		if mask&(1<<i) == 0 {
			continue
		}
		root := fmt.Sprintf("%c:\\", 'A'+i)
		path, err := windows.UTF16PtrFromString(root)
		if err != nil {
			continue
		}
		kind := windows.GetDriveType(path)
		if kind == windows.DRIVE_FIXED || kind == windows.DRIVE_REMOVABLE || kind == windows.DRIVE_RAMDISK {
			volumes = append(volumes, DocumentVolume{Path: root, Name: root[:2]})
		}
	}
	return volumes
}
