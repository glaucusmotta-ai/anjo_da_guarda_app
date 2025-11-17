import org.gradle.api.file.Directory
import org.gradle.api.tasks.Delete

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()

// build/ passa a ficar em ../../build em vez do padrão
rootProject.layout.buildDirectory.set(newBuildDir)

subprojects {
    // Cada subprojeto (app etc.) usa uma subpasta dentro desse build/
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    layout.buildDirectory.set(newSubprojectBuildDir)

    // Só descomente se REALMENTE precisar que :app seja avaliado antes dos demais:
    // evaluationDependsOn(":app")
}

// Tarefa padrão de limpeza
tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
