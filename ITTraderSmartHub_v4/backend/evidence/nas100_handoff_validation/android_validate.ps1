param([switch]$Assemble)
$ErrorActionPreference='Stop'
$taskWorkspace='C:\Users\MJ\Documents\Codex\2026-11-05\c-users-mj-documents-ittradesmart-nas100\work'
$env:ANDROID_USER_HOME=Join-Path $taskWorkspace 'android-user-final'
New-Item -ItemType Directory -Force -Path $env:ANDROID_USER_HOME | Out-Null
$env:GRADLE_USER_HOME='C:\Users\MJ\.gradle'
$env:JAVA_TOOL_OPTIONS='-Duser.home=C:/Users/MJ -Djava.io.tmpdir=C:/Users/MJ/Documents/Codex/2026-11-05/c-users-mj-documents-ittradesmart-nas100/work/java-temp'
$env:GRADLE_OPTS='-Dorg.gradle.native.dir=C:/Users/MJ/Documents/Codex/2026-11-05/c-users-mj-documents-ittradesmart-nas100/work/gradle-native'
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot'
$env:ANDROID_HOME='C:\Users\MJ\AppData\Local\Android\Sdk'
Set-Location -LiteralPath (Join-Path $taskWorkspace 'integration\ITTraderSmartHub_v4\android_project')
[string[]]$tasks=if ($Assemble) { @('assembleDebug') } else { @('testDebugUnitTest', 'lintDebug') }
$logName=if ($Assemble) { 'android_assemble.txt' } else { 'android_final.txt' }
& 'C:\Users\MJ\.gradle\wrapper\dists\gradle-8.7-all\aan3ydargesu18aqyqjwhr3pc\gradle-8.7\bin\gradle.bat' --offline --no-daemon '-Dorg.gradle.java.home=C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot' '-Pkotlin.compiler.execution.strategy=in-process' '-Pkotlin.incremental=false' @tasks 2>&1 | Tee-Object -FilePath (Join-Path $taskWorkspace $logName)
exit $LASTEXITCODE
