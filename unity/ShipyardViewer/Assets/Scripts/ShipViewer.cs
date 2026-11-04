using System.Collections;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Scripting;

/// <summary>샘플 모델 조립, 궤도 카메라, 브라우저 계약(SetView, 준비 신호).</summary>
public class ShipViewer : MonoBehaviour
{
    public Camera viewCamera;
    public Material hullLower, hullUpper, deck, house, accent, glass, steel, ground;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ShipViewer_NotifyReady();
#else
    static void ShipViewer_NotifyReady() { }
#endif

    const float Damping = 12f, MinPitch = 4f, MaxPitch = 88f, MinDistance = 50f, MaxDistance = 260f;
    const float PivotX = 10f, PivotMinY = 2f, PivotMaxY = 14f, PivotZ = 14f, FitMargin = 1.15f;
    static readonly Vector3 DefaultPivot = new Vector3(0f, 7f, 0f);

    struct View
    {
        public float Yaw, Pitch, Width, Height;
        public View(float yaw, float pitch, float width, float height) { Yaw = yaw; Pitch = pitch; Width = width; Height = height; }
    }

    static readonly View Reset = new View(-130f, 20f, 34f, 15f);
    static readonly View Front = new View(180f, 6f, 10f, 15f);
    static readonly View Side = new View(-90f, 6f, 33f, 15f);
    static readonly View Top = new View(-90f, 88f, 33f, 10f);

    float yaw, pitch, distance, targetYaw, targetPitch, targetDistance;
    Vector3 pivot, targetPivot, lastMouse;
    View? fitted;
    float fittedAspect;
    Mesh cube;

    void Awake()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = false;
#endif
        QualitySettings.shadows = ShadowQuality.All;
        QualitySettings.shadowDistance = 400f;
    }

    IEnumerator Start()
    {
        BuildScene();
        ApplyView(Reset);
        Snap();
        Place();
        yield return null;
        yield return new WaitForEndOfFrame();
        ShipViewer_NotifyReady();
    }

    GameObject Part(string name, Mesh mesh, params Material[] materials)
    {
        var part = new GameObject(name);
        part.transform.SetParent(transform, false);
        part.AddComponent<MeshFilter>().sharedMesh = mesh;
        part.AddComponent<MeshRenderer>().sharedMaterials = materials;
        return part;
    }

    GameObject Box(string name, Material material, Vector3 center, Vector3 size)
    {
        GameObject part = Part(name, cube, material);
        part.transform.localPosition = center;
        part.transform.localScale = size;
        return part;
    }

    void BuildScene()
    {
        cube = ShipModel.BuildCube();
        Part("Hull", ShipModel.BuildHull(), hullLower, hullUpper, deck);
        float d = ShipModel.DeckY;

        Box("Ground", ground, new Vector3(0f, -.005f, 0f), new Vector3(800f, .01f, 800f));
        for (int i = 0; i < 9; i++)
            Box("KeelBlock", steel, new Vector3(0f, .4f, -22f + i * 5.5f), new Vector3(3.4f, .8f, 1.8f));

        // 3단 선실, 브리지, 윙
        Box("HouseA", house, new Vector3(0f, d + 1.6f, -19.5f), new Vector3(9f, 3.2f, 10.5f));
        Box("HouseB", house, new Vector3(0f, d + 4.3f, -20f), new Vector3(8f, 2.2f, 9f));
        Box("HouseC", house, new Vector3(0f, d + 6.4f, -20f), new Vector3(7f, 2f, 8f));
        Box("Bridge", house, new Vector3(0f, d + 8.4f, -19.5f), new Vector3(6f, 2f, 6f));
        Box("BridgeWing", house, new Vector3(0f, d + 9.55f, -19.5f), new Vector3(10.6f, .3f, 4.4f));

        // 창
        Box("WindowA", glass, new Vector3(0f, d + 2f, -14.2f), new Vector3(6f, .5f, .1f));
        Box("WindowB", glass, new Vector3(0f, d + 4.5f, -15.45f), new Vector3(6f, .5f, .1f));
        Box("WindowC", glass, new Vector3(0f, d + 6.5f, -15.95f), new Vector3(5.2f, .5f, .1f));
        Box("WindowBridge", glass, new Vector3(0f, d + 8.5f, -16.45f), new Vector3(5.4f, 1f, .1f));
        Box("WindowPort", glass, new Vector3(-3.05f, d + 8.5f, -19.5f), new Vector3(.1f, .7f, 4.6f));
        Box("WindowStarboard", glass, new Vector3(3.05f, d + 8.5f, -19.5f), new Vector3(.1f, .7f, 4.6f));

        // 굴뚝
        Box("Funnel", accent, new Vector3(0f, d + 6.7f, -25f), new Vector3(2.8f, 7f, 3.6f));
        Box("FunnelCap", steel, new Vector3(0f, d + 10.6f, -25f), new Vector3(3f, .5f, 3.8f));

        // 마스트
        Box("Mast", steel, new Vector3(0f, d + 11.4f, -19.5f), new Vector3(.25f, 3.4f, .25f));
        Box("MastBar", steel, new Vector3(0f, d + 12f, -19.5f), new Vector3(2.2f, .15f, .15f));

        // 해치
        for (int i = 0; i < 4; i++)
        {
            float z = -9.5f + i * 8.2f;
            Box("HatchCoaming", accent, new Vector3(0f, d + .35f, z), new Vector3(6.8f, .7f, 7f));
            Box("HatchCover", steel, new Vector3(0f, d + .75f, z), new Vector3(6.3f, .12f, 6.5f));
        }

        // 카고 포스트
        for (int i = 0; i < 3; i++)
        {
            float z = -12.8f + i * 16.1f;
            Box("CargoPost", steel, new Vector3(0f, d + 3f, z), new Vector3(.9f, 6f, .9f));
            Box("CargoBoom", steel, new Vector3(0f, d + 5.8f, z + 3f), new Vector3(.35f, .35f, 6f));
        }
    }

    float FitDistance(View view)
    {
        float tangent = Mathf.Tan(viewCamera.fieldOfView * .5f * Mathf.Deg2Rad);
        float fit = Mathf.Max(view.Width / (tangent * viewCamera.aspect), view.Height / tangent) * FitMargin;
        return Mathf.Clamp(fit, MinDistance, MaxDistance);
    }

    void ApplyView(View view)
    {
        targetYaw = yaw + Mathf.DeltaAngle(yaw, view.Yaw);
        targetPitch = view.Pitch;
        targetPivot = DefaultPivot;
        targetDistance = FitDistance(view);
        fitted = view;
        fittedAspect = viewCamera.aspect;
    }

    void Snap()
    {
        yaw = targetYaw;
        pitch = targetPitch;
        distance = targetDistance;
        pivot = targetPivot;
    }

    [Preserve]
    public void SetView(string name)
    {
        switch (name)
        {
            case "front": ApplyView(Front); break;
            case "side": ApplyView(Side); break;
            case "top": ApplyView(Top); break;
            case "reset": ApplyView(Reset); break;
        }
    }

    void ReadInput()
    {
        Vector3 mouse = Input.mousePosition;
        Vector3 delta = mouse - lastMouse;
        lastMouse = mouse;

        if (Input.GetMouseButton(0))
        {
            targetYaw += delta.x * .3f;
            targetPitch = Mathf.Clamp(targetPitch - delta.y * .25f, MinPitch, MaxPitch);
            fitted = null;
        }
        else if (Input.GetMouseButton(1))
        {
            float tangent = Mathf.Tan(viewCamera.fieldOfView * .5f * Mathf.Deg2Rad);
            float unitsPerPixel = 2f * distance * tangent / Mathf.Max(1, Screen.height);
            Transform t = viewCamera.transform;
            Vector3 moved = targetPivot - t.right * (delta.x * unitsPerPixel) - t.up * (delta.y * unitsPerPixel);
            targetPivot = new Vector3(
                Mathf.Clamp(moved.x, -PivotX, PivotX), Mathf.Clamp(moved.y, PivotMinY, PivotMaxY), Mathf.Clamp(moved.z, -PivotZ, PivotZ));
            fitted = null;
        }

        float wheel = Mathf.Clamp(Input.mouseScrollDelta.y, -3f, 3f);
        if (wheel != 0f)
        {
            targetDistance = Mathf.Clamp(targetDistance * Mathf.Exp(-wheel * .12f), MinDistance, MaxDistance);
            fitted = null;
        }
    }

    static float Approach(float current, float target, float blend, float epsilon)
    {
        float next = Mathf.Lerp(current, target, blend);
        return Mathf.Abs(next - target) < epsilon ? target : next;
    }

    void Follow()
    {
        float blend = 1f - Mathf.Exp(-Damping * Time.unscaledDeltaTime);
        yaw = Approach(yaw, targetYaw, blend, .002f);
        pitch = Approach(pitch, targetPitch, blend, .002f);
        distance = Approach(distance, targetDistance, blend, .002f);
        pivot = (pivot - targetPivot).sqrMagnitude < 1e-6f ? targetPivot : Vector3.Lerp(pivot, targetPivot, blend);
    }

    void Place()
    {
        Quaternion rotation = Quaternion.Euler(pitch, yaw, 0f);
        Transform t = viewCamera.transform;
        t.SetPositionAndRotation(pivot - rotation * Vector3.forward * distance, rotation);
    }

    void Update()
    {
        if (cube == null) return;
        ReadInput();
        if (fitted.HasValue && !Mathf.Approximately(fittedAspect, viewCamera.aspect))
        {
            fittedAspect = viewCamera.aspect;
            targetDistance = FitDistance(fitted.Value);
        }
        Follow();
        Place();
    }
}
