from pathlib import Path
import shutil
import sys


def replace(path, old, new, count=-1):
    p = Path(path)
    s = p.read_text()
    if old not in s:
        raise ValueError("Native patch anchor absent in " + path)
    p.write_text(s.replace(old, new, count))


path = "internal/arduino/httpclient/httpclient.go"
replace(path, '"context"', '"context"\n "fmt"\n "os"')
anchor = "func DownloadFile(ctx context.Context, path *paths.Path, URL string, queryParameter string, label string, downloadCB rpc.DownloadProgressCB, config downloader.Config) (returnedError error) {"
replace(
    path,
    anchor,
    anchor
    + '\n if os.Getenv("ARDUINO_PURIFIER_FROZEN")=="1" { return fmt.Errorf("dependencies are Nix-resolved; use arduino-purifier lock --update") }\n if handled,err:=purifierReplay(path.String(),URL);handled{return err}\n originalURL:=URL\n defer func(){if returnedError==nil{returnedError=purifierCapture(path.String(),originalURL)}}()',
)
shutil.copyfile(sys.argv[1], "internal/arduino/httpclient/purifier_capture.go")
path = "internal/arduino/cores/tools.go"
replace(path, '"regexp"', '"regexp"\n "os"')
replace(
    path,
    "return tr.GetFlavourCompatibleWith(runtime.GOOS, runtime.GOARCH)",
    'if os.Getenv("ARDUINO_PURIFIER_CAPTURE")!="" && os.Getenv("ARDUINO_PURIFIER_ARCH")!="" { return tr.GetFlavourCompatibleWith(runtime.GOOS,os.Getenv("ARDUINO_PURIFIER_ARCH")) }\n return tr.GetFlavourCompatibleWith(runtime.GOOS, runtime.GOARCH)',
)
# Keep dependency mutations inside the native SDK scoped to a frozen invocation.
for path, anchors in [
    (
        "internal/arduino/resources/install.go",
        [
            "func (release *DownloadResource) Install(downloadDir, tempPath, destDir *paths.Path, checks IntegrityCheckMode) error {"
        ],
    ),
    (
        "internal/arduino/cores/packagemanager/install_uninstall.go",
        [
            "func (pme *Explorer) InstallPlatform(platformRelease *cores.PlatformRelease, checks resources.IntegrityCheckMode) error {",
            "func (pme *Explorer) InstallPlatformInDirectory(platformRelease *cores.PlatformRelease, destDir *paths.Path, checks resources.IntegrityCheckMode) error {",
            "func (pme *Explorer) UninstallPlatform(platformRelease *cores.PlatformRelease, taskCB rpc.TaskProgressCB, skipPreUninstall bool) error {",
            "func (pme *Explorer) InstallTool(toolRelease *cores.ToolRelease, taskCB rpc.TaskProgressCB, skipPostInstall bool, checks resources.IntegrityCheckMode) error {",
            "func (pme *Explorer) UninstallTool(toolRelease *cores.ToolRelease, taskCB rpc.TaskProgressCB, skipPreUninstall bool) error {",
        ],
    ),
    (
        "internal/arduino/libraries/librariesmanager/install.go",
        [
            "func (lmi *Installer) Uninstall(lib *libraries.Library) error {",
            "func (lmi *Installer) InstallZipLib(ctx context.Context, archivePath *paths.Path, overwrite bool) error {",
            "func (lmi *Installer) InstallGitLib(argURL string, overwrite bool) error {",
        ],
    ),
]:
    text = Path(path).read_text()
    for module in ['"os"', '"fmt"']:
        if "\t" + module + "\n" not in text:
            replace(path, "import (", "import (\n " + module)
    for anchor in anchors:
        replace(
            path,
            anchor,
            anchor
            + '\n if os.Getenv("ARDUINO_PURIFIER_FROZEN")=="1" { return fmt.Errorf("dependencies are Nix-resolved; use arduino-purifier lock --update") }',
        )
shutil.copyfile(sys.argv[2], "internal/cli/purifier_project.go")
replace(
    "internal/cli/cli.go",
    "cmd.AddCommand(board.NewCommand(srv))",
    "cmd.AddCommand(purifierProjectCmd())\n cmd.AddCommand(board.NewCommand(srv))",
)
