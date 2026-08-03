/** Android: skip Reanimated/Worklets native modules — RN 0.86 startup crash on release builds. */
module.exports = {
  dependencies: {
    'react-native-reanimated': {
      platforms: {
        android: null,
      },
    },
    'react-native-worklets': {
      platforms: {
        android: null,
      },
    },
  },
};
