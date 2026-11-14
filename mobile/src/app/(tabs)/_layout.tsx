import { Redirect, Tabs } from "expo-router";
import {
  ChartNoAxesCombined,
  FlaskConical,
  House,
  Layers,
  UserRound,
} from "lucide-react-native";
import { View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Loading } from "../../components/ui";
import { useSession } from "../../providers";
import { colors } from "../../theme";

export default function TabLayout() {
  const { user, ready } = useSession();
  const insets = useSafeAreaInsets();
  if (!ready)
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Loading />
      </View>
    );
  if (!user) return <Redirect href="/login" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.green,
        tabBarInactiveTintColor: colors.faint,
        tabBarStyle: {
          backgroundColor: colors.bg,
          borderTopColor: colors.line,
          paddingTop: 8,
          height: 64 + Math.max(10, insets.bottom),
          paddingBottom: Math.max(10, insets.bottom),
        },
        tabBarLabelStyle: { fontSize: 10, marginTop: 4 },
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Overview",
          tabBarIcon: ({ color }) => <House size={20} color={color} />,
        }}
      />
      <Tabs.Screen
        name="holdings"
        options={{
          title: "Holdings",
          tabBarIcon: ({ color }) => <Layers size={20} color={color} />,
        }}
      />
      <Tabs.Screen
        name="analytics"
        options={{
          title: "Analytics",
          tabBarIcon: ({ color }) => (
            <ChartNoAxesCombined size={20} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="scenarios"
        options={{
          title: "Scenarios",
          tabBarIcon: ({ color }) => <FlaskConical size={20} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color }) => <UserRound size={20} color={color} />,
        }}
      />
    </Tabs>
  );
}
