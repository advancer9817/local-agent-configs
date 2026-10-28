package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func uploadProducts(ctx context.Context, c Config, products []Product, root, sharedRoot string, log func(string)) error {
	if err := c.validate(true, false); err != nil {
		return err
	}
	target := strings.TrimRight(c.API, "/") + "/" + c.Bank
	count := 0
	for _, p := range products {
		if p.Status != "approved" {
			continue
		}
		body, err := os.ReadFile(filepath.Join(root, "products", p.ID+".md"))
		if err != nil || hashText(string(body)) != p.SHA {
			return errors.New("预览正文指纹不匹配，拒绝确认入库")
		}
		if p.JobID == "" || p.Target != target {
			return errors.New("该预览不是当前服务端任务，请重新提交来源")
		}
		var before RemoteJob
		if err = requestJSON(ctx, "GET", ingestURL(c, "/jobs/"+p.JobID+"?preview=true"), c.Token, nil, &before); err != nil {
			return err
		}
		if before.ID != p.JobID || before.Text != string(body) || (before.Status != "prepared" && before.Status != "retaining" && before.Status != "completed") {
			return errors.New("服务端预览或任务状态已变化，未确认入库")
		}
		if before.Status == "prepared" {
			var committed RemoteJob
			if err = requestJSON(ctx, "POST", ingestURL(c, "/jobs/"+p.JobID+"/commit"), c.Token, map[string]any{}, &committed); err != nil {
				return err
			}
		}
		if _, err = waitIngest(ctx, c, p.JobID, false); err != nil {
			return err
		}
		count++
		log("服务端确认已入库：" + p.Title)
	}
	if count == 0 {
		return errors.New("没有可确认的服务端成品")
	}
	log(fmt.Sprintf("%d 份成品已确认落库；远端已有文档未删除", count))
	return nil
}
