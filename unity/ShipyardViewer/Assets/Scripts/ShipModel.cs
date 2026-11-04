using System.Collections.Generic;
using UnityEngine;

/// <summary>Demo Ship 01. 실제 호선 형상이 아니다. 메시는 런타임에 코드로 만든다.</summary>
public static class ShipModel
{
    const float Length = 60f, Beam = 10f, Depth = 6f, Keel = .8f, Waterline = 2.6f, BowRake = 3f;
    const int Stations = 72;
    static readonly float[] Rows = { 0f, .2f, .5f, .9f, 1.3f, 1.6f, 2.1f, 2.6f, 3.2f, 4f, 5f, 5.6f, 6f };
    const int Lower = 0, Upper = 1, DeckPart = 2;

    public static float DeckY => Keel + Depth;

    static float HalfWidth(float z, float h)
    {
        float section = 1f - .55f * Mathf.Pow(1f - Mathf.Clamp01(h / 1.6f), 3f);
        float zs = z - BowRake * (h / Depth);
        float plan = 1f;
        if (zs > 12f) plan = 1f - Mathf.Pow(Mathf.Clamp01((zs - 12f) / 15f), 2.2f);
        if (z < -18f)
        {
            float s = Mathf.Clamp01((-18f - z) / 12f);
            plan *= 1f - .28f * s * s;
            section *= Mathf.Pow(Mathf.Clamp01((h + .15f) / 6f), .7f * s);
        }
        return Beam / 2f * section * plan;
    }

    static float StationZ(int i) => -Length / 2f + Length * i / (Stations - 1);

    class Builder
    {
        public readonly List<Vector3> Vertices = new List<Vector3>();
        public readonly List<int>[] Parts = { new List<int>(), new List<int>(), new List<int>() };

        public void Triangle(int part, int a, int b, int c, Vector3 outward)
        {
            Vector3 normal = Vector3.Cross(Vertices[b] - Vertices[a], Vertices[c] - Vertices[a]);
            if (normal.sqrMagnitude < 1e-10f) return;
            bool flip = Vector3.Dot(normal, outward) < 0f;
            Parts[part].Add(a);
            Parts[part].Add(flip ? c : b);
            Parts[part].Add(flip ? b : c);
        }

        public void Quad(int part, int a, int b, int c, int d, Vector3 outward)
        {
            Triangle(part, a, b, c, outward);
            Triangle(part, a, c, d, outward);
        }

        /// <summary>각진 면: 정점을 공유하지 않는다.</summary>
        public void FlatQuad(int part, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 outward)
        {
            int start = Vertices.Count;
            Vertices.AddRange(new[] { a, b, c, d });
            Quad(part, start, start + 1, start + 2, start + 3, outward);
        }
    }

    static void AddShell(Builder builder, float side)
    {
        // 곡면 법선을 위해 현 안에서는 정점을 병합하되 x=0에서 좌우를 공유하지 않는다.
        int start = builder.Vertices.Count;
        int rows = Rows.Length;
        for (int i = 0; i < Stations; i++)
            for (int j = 0; j < rows; j++)
            {
                float z = StationZ(i);
                builder.Vertices.Add(new Vector3(side * HalfWidth(z, Rows[j]), Keel + Rows[j], z));
            }
        Vector3 outward = new Vector3(side, 0f, 0f);
        for (int i = 0; i < Stations - 1; i++)
            for (int j = 0; j < rows - 1; j++)
            {
                int a = start + i * rows + j;
                int b = a + rows;
                builder.Quad(Rows[j] < Waterline ? Lower : Upper, a, b, b + 1, a + 1, outward);
            }
    }

    static Vector3 Edge(float side, float z, float h) => new Vector3(side * HalfWidth(z, h), Keel + h, z);

    public static Mesh BuildHull()
    {
        var builder = new Builder();
        AddShell(builder, -1f);
        AddShell(builder, 1f);
        for (int i = 0; i < Stations - 1; i++)
        {
            float z0 = StationZ(i), z1 = StationZ(i + 1);
            builder.FlatQuad(Lower, Edge(-1f, z0, 0f), Edge(1f, z0, 0f), Edge(1f, z1, 0f), Edge(-1f, z1, 0f), Vector3.down);
            builder.FlatQuad(DeckPart, Edge(-1f, z0, Depth), Edge(1f, z0, Depth), Edge(1f, z1, Depth), Edge(-1f, z1, Depth), Vector3.up);
        }
        float stern = StationZ(0);
        for (int j = 0; j < Rows.Length - 1; j++)
        {
            int part = Rows[j] < Waterline ? Lower : Upper;
            builder.FlatQuad(part, Edge(-1f, stern, Rows[j]), Edge(1f, stern, Rows[j]), Edge(1f, stern, Rows[j + 1]), Edge(-1f, stern, Rows[j + 1]), Vector3.back);
        }

        var mesh = new Mesh { name = "DemoShipHull" };
        mesh.SetVertices(builder.Vertices);
        mesh.subMeshCount = builder.Parts.Length;
        for (int part = 0; part < builder.Parts.Length; part++) mesh.SetTriangles(builder.Parts[part], part);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    public static Mesh BuildCube()
    {
        var vertices = new List<Vector3>();
        var triangles = new List<int>();
        Vector3[] normals = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
        foreach (Vector3 n in normals)
        {
            Vector3 u = Mathf.Abs(n.y) > .5f ? Vector3.right : Vector3.up;
            Vector3 v = Vector3.Cross(n, u);
            int start = vertices.Count;
            vertices.Add((n - u - v) * .5f);
            vertices.Add((n + u - v) * .5f);
            vertices.Add((n + u + v) * .5f);
            vertices.Add((n - u + v) * .5f);
            triangles.AddRange(new[] { start, start + 1, start + 2, start, start + 2, start + 3 });
        }
        var mesh = new Mesh { name = "UnitCube" };
        mesh.SetVertices(vertices);
        mesh.SetTriangles(triangles, 0);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }
}
