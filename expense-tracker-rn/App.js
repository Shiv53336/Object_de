import 'react-native-gesture-handler';
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { AppProvider } from './src/context/AppContext';
import HomeScreen      from './src/screens/HomeScreen';
import StatsScreen     from './src/screens/StatsScreen';
import RecurringScreen from './src/screens/RecurringScreen';
import SettingsScreen  from './src/screens/SettingsScreen';

const Tab = createBottomTabNavigator();

const COLORS = {
  bg:   '#FAF6F1',
  navy: '#3D405B',
  mid:  '#8B8580',
};

function TabIcon({ emoji, focused }) {
  return (
    <View style={{ alignItems: 'center' }}>
      <Text style={{ fontSize: 22, opacity: focused ? 1 : 0.45 }}>{emoji}</Text>
    </View>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <NavigationContainer>
          <StatusBar style="dark" backgroundColor={COLORS.bg} />
          <Tab.Navigator
            screenOptions={{
              headerShown:   false,
              tabBarStyle:   {
                backgroundColor: 'rgba(255,255,255,0.97)',
                borderTopColor:  '#EDE8E1',
                borderTopWidth:  1,
                paddingBottom:   8,
                paddingTop:      8,
                height:          64,
              },
              tabBarActiveTintColor:   COLORS.navy,
              tabBarInactiveTintColor: COLORS.mid,
              tabBarLabelStyle: {
                fontSize:   10,
                fontWeight: '600',
                marginTop:  2,
              },
            }}
          >
            <Tab.Screen
              name="Home"
              component={HomeScreen}
              options={{ tabBarIcon: ({ focused }) => <TabIcon emoji="🏠" focused={focused} /> }}
            />
            <Tab.Screen
              name="Stats"
              component={StatsScreen}
              options={{ tabBarIcon: ({ focused }) => <TabIcon emoji="📊" focused={focused} /> }}
            />
            <Tab.Screen
              name="Recurring"
              component={RecurringScreen}
              options={{ tabBarIcon: ({ focused }) => <TabIcon emoji="🔄" focused={focused} /> }}
            />
            <Tab.Screen
              name="Settings"
              component={SettingsScreen}
              options={{ tabBarIcon: ({ focused }) => <TabIcon emoji="⚙️" focused={focused} /> }}
            />
          </Tab.Navigator>
        </NavigationContainer>
      </AppProvider>
    </SafeAreaProvider>
  );
}
