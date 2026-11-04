package cli

import (
 "encoding/json"
 "fmt"
 "os"
 "github.com/arduino/arduino-cli/internal/arduino/sketch"
 "github.com/arduino/go-paths-helper"
 "github.com/spf13/cobra"
)

func purifierProjectCmd() *cobra.Command {
 return &cobra.Command{Use:"purifier-project PATH",Hidden:true,Args:cobra.ExactArgs(1),RunE:func(cmd *cobra.Command,args []string) error {
  native,err:=sketch.New(paths.New(args[0]));if err!=nil{return err}
  if native.Project==nil || len(native.Project.Profiles)==0 { return fmt.Errorf("add a native pinned sketch.yaml profile before locking") }
  profiles:=[]map[string]interface{}{}
  project:=*native.Project
  project.DefaultFqbn="";project.DefaultPort="";project.DefaultPortConfig=nil;project.DefaultProtocol="";project.DefaultProgrammer=""
  project.Profiles=nil
  for _,profile:=range native.Project.Profiles {
   if profile.FQBN=="" {return fmt.Errorf("profile %s needs an FQBN",profile.Name)}
   if len(profile.Platforms)==0 {return fmt.Errorf("profile %s needs a pinned platform",profile.Name)}
   for _,platform:=range profile.Platforms {
    if platform.Version==nil || platform.Packager!="arduino" || platform.Architecture!="avr" {return fmt.Errorf("the initial provider supports pinned Arduino AVR profiles")}
   }
   for _,library:=range profile.Libraries {
    if library.InstallDir!=nil || library.Version==nil {return fmt.Errorf("the initial provider supports pinned registry libraries")}
   }
   copy:=*profile;copy.Notes="";copy.Port="";copy.PortConfig=nil;copy.Protocol="";copy.Programmer=""
   project.Profiles=append(project.Profiles,&copy)
   profiles=append(profiles,map[string]interface{}{"name":profile.Name,"fqbn":profile.FQBN,"platforms":profile.Platforms,"libraries":profile.Libraries})
  }
  return json.NewEncoder(os.Stdout).Encode(map[string]interface{}{"defaultProfile":native.Project.DefaultProfile,"profiles":profiles,"sketchYaml":project.AsYaml()})
 }}
}
