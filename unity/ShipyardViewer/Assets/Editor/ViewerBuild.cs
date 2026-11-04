using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

/// <summary>씬·재질 재생성 후 Web 빌드. -batchmode -quit -buildTarget WebGL -executeMethod ViewerBuild.Build</summary>
public static class ViewerBuild
{
    const string GeneratedDir = "Assets/Generated";
    const string ScenePath = GeneratedDir + "/Viewer.unity";
    const string OutputDir = "../../frontend/public/unity/ship-viewer";
    const string ProductName = "ShipyardViewer", CompanyName = "SWP", ProductVersion = "1.0.0";

    [System.Serializable]
    class BuildManifest
    {
        public string loaderUrl, dataUrl, frameworkUrl, codeUrl, companyName, productName, productVersion;
    }

    static Color Hex(string value)
    {
        ColorUtility.TryParseHtmlString(value, out Color color);
        return color;
    }

    static Material CreateMaterial(string name, string hex, float smoothness)
    {
        var material = new Material(Shader.Find("Standard")) { name = name };
        material.SetColor("_Color", Hex(hex));
        material.SetFloat("_Glossiness", smoothness);
        material.SetFloat("_Metallic", 0f);
        AssetDatabase.CreateAsset(material, $"{GeneratedDir}/{name}.mat");
        return material;
    }

    static void CreateScene()
    {
        if (AssetDatabase.IsValidFolder(GeneratedDir)) AssetDatabase.DeleteAsset(GeneratedDir);
        AssetDatabase.CreateFolder("Assets", "Generated");
        Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var cameraObject = new GameObject("Main Camera") { tag = "MainCamera" };
        var camera = cameraObject.AddComponent<Camera>();
        camera.clearFlags = CameraClearFlags.SolidColor;
        camera.backgroundColor = Hex("#DDE4EE");
        camera.fieldOfView = 30f;
        camera.nearClipPlane = 1f;
        camera.farClipPlane = 1000f;

        var sunObject = new GameObject("Sun");
        var sun = sunObject.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = .95f;
        sun.shadows = LightShadows.Soft;
        sunObject.transform.rotation = Quaternion.Euler(52f, -35f, 0f);

        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);
        RenderSettings.skybox = null;

        var viewerObject = new GameObject("ShipViewer");
        var viewer = viewerObject.AddComponent<ShipViewer>();
        viewer.viewCamera = camera;
        viewer.hullLower = CreateMaterial("HullLower", "#9E2F2A", .3f);
        viewer.hullUpper = CreateMaterial("HullUpper", "#1B3A66", .4f);
        viewer.deck = CreateMaterial("Deck", "#6F8A7A", .2f);
        viewer.house = CreateMaterial("House", "#E4E8EE", .3f);
        viewer.accent = CreateMaterial("Accent", "#D97F2A", .3f);
        viewer.glass = CreateMaterial("Glass", "#202C3C", .8f);
        viewer.steel = CreateMaterial("Steel", "#5B6573", .3f);
        viewer.ground = CreateMaterial("Ground", "#B4BDC9", .05f);

        EditorSceneManager.SaveScene(scene, ScenePath);
        AssetDatabase.SaveAssets();
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
    }

    static void ApplyPlayerSettings()
    {
        PlayerSettings.companyName = CompanyName;
        PlayerSettings.productName = ProductName;
        PlayerSettings.bundleVersion = ProductVersion;
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.runInBackground = true;
        PlayerSettings.SplashScreen.show = false;
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.nameFilesAsHashes = false;
        PlayerSettings.WebGL.dataCaching = false;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.None;
        PlayerSettings.WebGL.template = "APPLICATION:Minimal";
        PlayerSettings.stripEngineCode = true;
        PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.High);
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.WebGL, new[] { GraphicsDeviceType.OpenGLES3 });
    }

    static void WriteManifest()
    {
        string buildDir = Path.Combine(OutputDir, "Build");
        string name = Path.GetFileName(OutputDir);
        var manifest = new BuildManifest
        {
            loaderUrl = $"{name}.loader.js", dataUrl = $"{name}.data", frameworkUrl = $"{name}.framework.js",
            codeUrl = $"{name}.wasm", companyName = CompanyName, productName = ProductName, productVersion = ProductVersion,
        };
        foreach (string file in new[] { manifest.loaderUrl, manifest.dataUrl, manifest.frameworkUrl, manifest.codeUrl })
            if (!File.Exists(Path.Combine(buildDir, file))) throw new BuildFailedException($"빌드 파일 없음: {file}");
        File.WriteAllText(Path.Combine(buildDir, "build.json"), JsonUtility.ToJson(manifest, true));
    }

    public static void Build()
    {
        CreateScene();
        ApplyPlayerSettings();
        if (Directory.Exists(OutputDir)) Directory.Delete(OutputDir, true);
        Directory.CreateDirectory(OutputDir);

        BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath }, locationPathName = OutputDir, target = BuildTarget.WebGL, options = BuildOptions.None,
        });
        if (report.summary.result != BuildResult.Succeeded) throw new BuildFailedException($"빌드 실패: {report.summary.result}");

        File.Delete(Path.Combine(OutputDir, "index.html"));
        string template = Path.Combine(OutputDir, "TemplateData");
        if (Directory.Exists(template)) Directory.Delete(template, true);
        WriteManifest();
    }
}
