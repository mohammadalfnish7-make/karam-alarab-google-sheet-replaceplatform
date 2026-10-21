import { Canvas, type ThreeEvent } from "@react-three/fiber"
import { Clone, OrbitControls, Text, useGLTF } from "@react-three/drei"
import { Suspense, useLayoutEffect, useMemo, useState } from "react"
import { Box3, Object3D, Vector3 } from "three"
import { planToPallets, type LoadingPlan, type PlanMark, type PlanPallet } from "../containerPlanLayout"

/** Euro pallet footprint (Grab3D wooden-pallet.glb ≈ 1.20 × 0.80 × 0.14 m). */
const PALLET_W = 1.2
const PALLET_D = 0.8
const PALLET_BASE_H = 0.14
const AISLE = 0.2
const ROW_GAP = 0.25
const WALL = 0.1
const CARGO_H = 2.5

const CAB_URL = "/models/truck.glb"
const PALLET_URL = "/models/pallet.glb"
const CARTON_URL = "/models/carton.glb"

type Props = {
  plan: LoadingPlan
  label?: string
}

export function Container3DView({ plan, label }: Props) {
  const pallets = useMemo(() => planToPallets(plan), [plan])
  const [shellOpen, setShellOpen] = useState(true)
  const [selectedMix, setSelectedMix] = useState<number | null>(null)

  const selected = selectedMix == null ? null : pallets.find((p) => p.mix === selectedMix) || null
  const maxMix = pallets.length ? Math.max(...pallets.map((p) => p.mix)) : 0
  const rows = Math.max(1, Math.ceil(maxMix / 2))

  if (!pallets.length) {
    return (
      <div className="container-3d-empty">
        <p className="muted">Upload a loading plan to see all pallets in 3D.</p>
      </div>
    )
  }

  const camZ = Math.max(14, rows * 1.1 + 8)

  return (
    <div className="container-3d">
      <div className="container-3d-toolbar">
        <span className="muted">
          {label ? `${label} · ` : ""}
          {pallets.length} pallets · P1 at front (inside)
          {plan?.container_number ? ` · cont ${plan.container_number}` : ""}
        </span>
        <button className="btn" type="button" onClick={() => setShellOpen((v) => !v)}>
          {shellOpen ? "Close sides & roof" : "Open sides & roof"}
        </button>
      </div>
      <div className="container-3d-body">
        <div className="container-3d-canvas">
          <Canvas
            camera={{ position: [camZ * 0.5, 10, camZ * 0.7], fov: 40, near: 0.1, far: 250 }}
            onPointerMissed={() => setSelectedMix(null)}
          >
            <color attach="background" args={["#dce6f4"]} />
            <ambientLight intensity={0.8} />
            <directionalLight position={[14, 20, 10]} intensity={1.2} castShadow />
            <Suspense fallback={null}>
              <TruckScene
                pallets={pallets}
                rows={rows}
                shellOpen={shellOpen}
                selectedMix={selectedMix}
                onToggleShell={() => setShellOpen((v) => !v)}
                onSelect={(mix) => setSelectedMix(mix)}
              />
            </Suspense>
            <OrbitControls makeDefault minDistance={6} maxDistance={60} target={[0, 1.2, 0]} />
          </Canvas>
        </div>
        <aside className="container-3d-panel">
          <h3>{selected ? `Pallet P${selected.mix}` : "Select a pallet"}</h3>
          {selected ? (
            <>
              <p className="muted">
                {selected.side} · <strong>{selected.marks.length}</strong> mark
                {selected.marks.length === 1 ? "" : "s"} from plan
              </p>
              <ul className="container-3d-marks">
                {selected.marks.map((mark, index) => (
                  <MarkCard key={`${selected.mix}-${index}`} mark={mark} />
                ))}
              </ul>
            </>
          ) : (
            <p className="muted">
              Sides and roof open for a clear view. Click a pallet for marks. P1 is at the front inside.
            </p>
          )}
        </aside>
      </div>
    </div>
  )
}

function MarkCard({ mark }: { mark: PlanMark }) {
  return (
    <li className="container-3d-mark">
      <strong>{mark.name}</strong>
      <dl>
        {mark.customer_code ? (
          <>
            <dt>Code</dt>
            <dd>{mark.customer_code}</dd>
          </>
        ) : null}
        <dt>CTN</dt>
        <dd>{mark.cartons ?? "—"}</dd>
        <dt>kg</dt>
        <dd>{mark.weight_kg ?? "—"}</dd>
      </dl>
    </li>
  )
}

function TruckScene({
  pallets,
  rows,
  shellOpen,
  selectedMix,
  onToggleShell,
  onSelect,
}: {
  pallets: PlanPallet[]
  rows: number
  shellOpen: boolean
  selectedMix: number | null
  onToggleShell: () => void
  onSelect: (mix: number) => void
}) {
  const innerW = PALLET_W * 2 + AISLE + 0.35
  const innerL = rows * (PALLET_D + ROW_GAP) + 0.55
  const outerW = innerW + WALL * 2
  const outerL = innerL + WALL * 2
  const outerH = CARGO_H + WALL

  const byMix = useMemo(() => {
    const map = new Map<number, PlanPallet>()
    for (const p of pallets) map.set(p.mix, p)
    return map
  }, [pallets])

  return (
    <group>
      <TruckCab width={outerW * 0.95} cargoFrontZ={-outerL / 2} />

      <CargoBay
        width={outerW}
        length={outerL}
        height={outerH}
        shellOpen={shellOpen}
        onToggleShell={onToggleShell}
      />

      <Text
        position={[0, outerH + 0.35, -outerL / 2 - 0.2]}
        fontSize={0.26}
        color="#0f3d1f"
        anchorX="center"
        anchorY="middle"
      >
        FRONT · P1
      </Text>
      <Text
        position={[0, outerH + 0.35, outerL / 2 + 0.25]}
        fontSize={0.26}
        color="#1432c6"
        anchorX="center"
        anchorY="middle"
      >
        DOOR
      </Text>

      {Array.from({ length: maxMixOf(pallets) }, (_, i) => i + 1).map((mix) => {
        const pallet = byMix.get(mix)
        if (!pallet) return null
        const row = Math.ceil(mix / 2) - 1
        const x = pallet.side === "left" ? -(PALLET_W / 2 + AISLE / 2) : PALLET_W / 2 + AISLE / 2
        // P1 deep inside at front (−Z); highest mixes at rear door (+Z)
        const z = -outerL / 2 + WALL + 0.45 + row * (PALLET_D + ROW_GAP) + PALLET_D / 2
        return (
          <LoadedPallet
            key={mix}
            mix={mix}
            position={[x, WALL, z]}
            selected={selectedMix === mix}
            markCount={pallet.marks.length}
            onSelect={onSelect}
          />
        )
      })}
    </group>
  )
}

/** Kenney Car Kit truck.glb (CC0) — cab / chassis at the front of the bay. */
function TruckCab({ width, cargoFrontZ }: { width: number; cargoFrontZ: number }) {
  const { scene } = useGLTF(CAB_URL)
  const root = useMemo(() => scene.clone(true), [scene])

  useLayoutEffect(() => {
    root.position.set(0, 0, 0)
    root.rotation.set(0, Math.PI, 0) // nose toward −Z (front of bay)
    root.scale.set(1, 1, 1)
    root.updateMatrixWorld(true)

    const box = new Box3().setFromObject(root)
    const size = box.getSize(new Vector3())
    if (size.x < 0.01) return

    root.scale.setScalar(width / size.x)
    root.updateMatrixWorld(true)

    const placed = new Box3().setFromObject(root)
    const center = placed.getCenter(new Vector3())
    // Grounded; cab rear meets cargo front
    root.position.set(-center.x, -placed.min.y, cargoFrontZ - 0.1 - placed.max.z)
  }, [root, width, cargoFrontZ])

  return <primitive object={root} />
}

function CargoBay({
  width,
  length,
  height,
  shellOpen,
  onToggleShell,
}: {
  width: number
  length: number
  height: number
  shellOpen: boolean
  onToggleShell: () => void
}) {
  const color = "#c45a28"
  return (
    <group>
      <mesh position={[0, WALL / 2, 0]} receiveShadow>
        <boxGeometry args={[width, WALL, length]} />
        <meshStandardMaterial color="#6e5a45" roughness={0.9} />
      </mesh>
      {/* Sides + roof open by default for a clear load view */}
      {!shellOpen ? (
        <>
          <Wall
            size={[WALL, height, length]}
            position={[-width / 2 + WALL / 2, height / 2, 0]}
            color={color}
            onClick={onToggleShell}
          />
          <Wall
            size={[WALL, height, length]}
            position={[width / 2 - WALL / 2, height / 2, 0]}
            color={color}
            onClick={onToggleShell}
          />
          <mesh
            position={[0, height + WALL / 2, 0]}
            onClick={(event: ThreeEvent<MouseEvent>) => {
              event.stopPropagation()
              onToggleShell()
            }}
          >
            <boxGeometry args={[width + 0.04, WALL, length + 0.04]} />
            <meshStandardMaterial color="#8f3a18" metalness={0.25} roughness={0.5} />
          </mesh>
        </>
      ) : null}
      <Wall
        size={[width, height, WALL]}
        position={[0, height / 2, -length / 2 + WALL / 2]}
        color="#9a3f1c"
        onClick={onToggleShell}
        solid
      />
      <Wall
        size={[width * 0.18, height, WALL]}
        position={[-width * 0.35, height / 2, length / 2 - WALL / 2]}
        color="#8a3818"
        onClick={onToggleShell}
        solid
      />
      <Wall
        size={[width * 0.18, height, WALL]}
        position={[width * 0.35, height / 2, length / 2 - WALL / 2]}
        color="#8a3818"
        onClick={onToggleShell}
        solid
      />
      <mesh position={[0, 0.12, 0]}>
        <boxGeometry args={[width * 0.22, 0.1, length * 0.95]} />
        <meshStandardMaterial color="#2a2f38" metalness={0.45} roughness={0.5} />
      </mesh>
    </group>
  )
}

function Wall({
  size,
  position,
  color,
  onClick,
  solid,
}: {
  size: [number, number, number]
  position: [number, number, number]
  color: string
  onClick: () => void
  solid?: boolean
}) {
  return (
    <mesh
      position={position}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation()
        onClick()
      }}
    >
      <boxGeometry args={size} />
      <meshStandardMaterial
        color={color}
        transparent={!solid}
        opacity={solid ? 1 : 0.55}
        depthWrite={Boolean(solid)}
        metalness={0.2}
        roughness={0.55}
      />
    </mesh>
  )
}

function LoadedPallet({
  mix,
  position,
  selected,
  markCount,
  onSelect,
}: {
  mix: number
  position: [number, number, number]
  selected: boolean
  markCount: number
  onSelect: (mix: number) => void
}) {
  const { scene: palletScene } = useGLTF(PALLET_URL)
  const { scene: cartonScene } = useGLTF(CARTON_URL)

  const palletScale = useMemo(() => fitXZ(palletScene, PALLET_W, PALLET_D), [palletScene])
  // One load stack filling almost the whole pallet (was tiny before)
  const cargoH = 1.05
  const cartonFit = useMemo(
    () => fitAndCenter(cartonScene, PALLET_W * 0.9, cargoH, PALLET_D * 0.9),
    [cartonScene],
  )
  const layers = Math.min(3, Math.max(1, markCount))

  return (
    <group position={position}>
      <group
        onClick={(event: ThreeEvent<MouseEvent>) => {
          event.stopPropagation()
          onSelect(mix)
        }}
      >
        <group scale={palletScale}>
          <Clone object={palletScene} />
        </group>
        {Array.from({ length: layers }, (_, layer) => (
          <group
            key={layer}
            position={[
              cartonFit.offset.x,
              PALLET_BASE_H + cartonFit.offset.y + layer * (cargoH * 0.92),
              cartonFit.offset.z,
            ]}
            scale={cartonFit.scale}
          >
            <Clone object={cartonScene} />
          </group>
        ))}
        {selected ? (
          <mesh position={[0, PALLET_BASE_H + (layers * cargoH) / 2, 0]}>
            <boxGeometry args={[PALLET_W + 0.06, layers * cargoH + 0.1, PALLET_D + 0.06]} />
            <meshStandardMaterial color="#1769ff" transparent opacity={0.2} depthWrite={false} />
          </mesh>
        ) : null}
      </group>
      <Text
        position={[0, PALLET_BASE_H + layers * cargoH + 0.12, 0]}
        fontSize={0.28}
        color={selected ? "#0a2a80" : "#1a1f2e"}
        anchorX="center"
        anchorY="middle"
      >
        {`P${mix}`}
      </Text>
    </group>
  )
}

function fitXZ(scene: Object3D, targetW: number, targetD: number): number {
  const box = new Box3().setFromObject(scene)
  const size = box.getSize(new Vector3())
  if (size.x < 0.001 || size.z < 0.001) return 1
  return Math.min(targetW / size.x, targetD / size.z)
}

/** Scale model to fill a box and return offset so it sits centered on the floor. */
function fitAndCenter(scene: Object3D, targetW: number, targetH: number, targetD: number) {
  const box = new Box3().setFromObject(scene)
  const size = box.getSize(new Vector3())
  const center = box.getCenter(new Vector3())
  if (size.x < 0.001 || size.y < 0.001 || size.z < 0.001) {
    return { scale: 1, offset: { x: 0, y: 0, z: 0 } }
  }
  const scale = Math.min(targetW / size.x, targetH / size.y, targetD / size.z)
  return {
    scale,
    offset: {
      x: -center.x * scale,
      y: -box.min.y * scale,
      z: -center.z * scale,
    },
  }
}

function maxMixOf(pallets: PlanPallet[]) {
  return pallets.length ? Math.max(...pallets.map((p) => p.mix)) : 0
}

useGLTF.preload(CAB_URL)
useGLTF.preload(PALLET_URL)
useGLTF.preload(CARTON_URL)
