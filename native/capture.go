package httpclient

import (
 "crypto/sha256"
 "encoding/hex"
 "encoding/json"
 "fmt"
 "io"
 "os"
 "path/filepath"
 "sync"
)
var purifierMu sync.Mutex
func purifierCapture(path, url string) error {
 dir:=os.Getenv("ARDUINO_PURIFIER_CAPTURE")
 if dir=="" { return nil }
 input,err:=os.Open(path); if err!=nil{return err}; defer input.Close()
 file,err:=os.CreateTemp(dir,"archive-"); if err!=nil{return err}
 digest:=sha256.New()
 _,err=io.Copy(io.MultiWriter(file,digest),input); file.Close(); if err!=nil{return err}
 hash:=hex.EncodeToString(digest.Sum(nil)); archive:=filepath.Join(dir,hash)
 if err=os.Rename(file.Name(),archive);err!=nil{return err}
 purifierMu.Lock();defer purifierMu.Unlock()
 output,err:=os.OpenFile(filepath.Join(dir,"records.jsonl"),os.O_CREATE|os.O_APPEND|os.O_WRONLY,0600)
 if err!=nil{return err};defer output.Close()
 return json.NewEncoder(output).Encode(map[string]string{"url":url,"sha256":hash,"archive":archive})
}
func purifierReplay(path, url string) (bool,error) {
 file:=os.Getenv("ARDUINO_PURIFIER_REPLAY")
 if file=="" { return false,nil }
 data,err:=os.ReadFile(file);if err!=nil{return true,err}
 var archives map[string]string
 if err=json.Unmarshal(data,&archives);err!=nil{return true,err}
 archive,ok:=archives[url];if !ok{return true,fmt.Errorf("native Arduino download absent from lock: %s",url)}
 input,err:=os.Open(archive);if err!=nil{return true,err};defer input.Close()
 if err=os.MkdirAll(filepath.Dir(path),0755);err!=nil{return true,err}
 output,err:=os.Create(path);if err!=nil{return true,err}
 _,err=io.Copy(output,input);closeErr:=output.Close();if err!=nil{return true,err};return true,closeErr
}
