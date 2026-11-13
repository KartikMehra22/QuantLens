import React, { useId, useState } from "react";
import { Pressable, Text, View } from "react-native";
import Svg, {
  Circle,
  Defs,
  G,
  Line,
  LinearGradient,
  Path,
  Stop,
  Text as SvgText,
} from "react-native-svg";
import { colors, s } from "../theme";
import { Holding } from "../types";

export function LineChart({
  points,
  color = colors.green,
  height = 190,
  labels = [],
}: {
  points: number[];
  color?: string;
  height?: number;
  labels?: string[];
}) {
  const id = `fill${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [width, setWidth] = useState(350);
  const [selected, setSelected] = useState<number | null>(null);
  if (points.length < 2)
    return (
      <Text style={s.small}>
        Add enough historical observations to display a chart.
      </Text>
    );
  const min = Math.min(...points),
    max = Math.max(...points);
  const range = max - min || Math.max(1, Math.abs(max) * 0.01);
  const x = (index: number) => 7 + (index / (points.length - 1)) * 786;
  const y = (value: number) => 14 + ((max - value) / range) * (height - 32);
  const path = points
    .map(
      (value, index) =>
        `${index === 0 ? "M" : "L"} ${x(index).toFixed(2)} ${y(value).toFixed(2)}`,
    )
    .join(" ");
  const pick = selected == null ? null : Math.min(selected, points.length - 1);
  return (
    <View style={{ gap: 9 }}>
      {pick != null && (
        <Text style={[s.small, { color }]}>
          {labels[pick] || `Observation ${pick + 1}`} ·{" "}
          {points[pick].toFixed(2)}
        </Text>
      )}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Inspect chart observation"
        onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
        onPress={(e) =>
          setSelected(
            Math.max(
              0,
              Math.min(
                points.length - 1,
                Math.round(
                  (e.nativeEvent.locationX / width) * (points.length - 1),
                ),
              ),
            ),
          )
        }
      >
        <Svg
          width="100%"
          height={height}
          viewBox={`0 0 800 ${height}`}
          preserveAspectRatio="none"
        >
          <Defs>
            <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={color} stopOpacity={0.2} />
              <Stop offset="1" stopColor={color} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          {[0.15, 0.5, 0.85].map((a) => (
            <Line
              key={a}
              x1="0"
              x2="800"
              y1={height * a}
              y2={height * a}
              stroke={colors.line}
              strokeDasharray="3 7"
            />
          ))}
          <Path
            d={`${path} L 793 ${height} L 7 ${height} Z`}
            fill={`url(#${id})`}
          />
          <Path
            d={path}
            fill="none"
            stroke={color}
            strokeWidth="2.4"
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
          />
          {pick != null && (
            <G>
              <Line
                x1={x(pick)}
                x2={x(pick)}
                y1={0}
                y2={height}
                stroke={colors.muted}
                strokeDasharray="3 4"
              />
              <Circle cx={x(pick)} cy={y(points[pick])} r={4} fill={color} />
            </G>
          )}
        </Svg>
      </Pressable>
      <View style={s.between}>
        <Text style={s.small}>{labels[0] || "Start"}</Text>
        <Text style={s.small}>{labels.at(-1) || "Latest"}</Text>
      </View>
    </View>
  );
}

export function AllocationDonut({ holdings }: { holdings: Holding[] }) {
  const radius = 70,
    circumference = 2 * Math.PI * radius;
  return (
    <Svg
      width={180}
      height={180}
      viewBox="0 0 180 180"
      accessibilityLabel="Portfolio allocation"
    >
      <Circle
        cx={90}
        cy={90}
        r={radius}
        fill="none"
        stroke={colors.line}
        strokeWidth={15}
      />
      {holdings.map((h, index) => {
        const position = holdings
          .slice(0, index)
          .reduce((total, item) => total + item.weight * circumference, 0);
        return (
          <Circle
            key={h.id}
            cx={90}
            cy={90}
            r={radius}
            fill="none"
            stroke={h.color}
            strokeWidth={15}
            strokeDasharray={`${Math.max(0, h.weight * circumference - 3)} ${circumference}`}
            strokeDashoffset={-position}
            transform="rotate(-90 90 90)"
          />
        );
      })}
      <SvgText
        x={90}
        y={87}
        textAnchor="middle"
        fill={colors.text}
        fontSize={30}
        fontWeight="500"
      >
        {holdings.length}
      </SvgText>
      <SvgText
        x={90}
        y={109}
        textAnchor="middle"
        fill={colors.muted}
        fontSize={11}
      >
        HOLDINGS
      </SvgText>
    </Svg>
  );
}
