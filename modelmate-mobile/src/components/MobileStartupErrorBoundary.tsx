import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { color, font } from '@/src/styles/tokens';

type Props = {
  children: ReactNode;
  onRetry?: () => void;
};

type State = {
  error: Error | null;
};

/** Ловит фatal-ошибки React при старте и показывает текст вместо мгновенного закрытия приложения. */
export class MobileStartupErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ModelMate startup]', error, info.componentStack);
  }

  private retry = () => {
    this.setState({ error: null });
    this.props.onRetry?.();
  };

  render() {
    if (!this.state.error) return this.props.children;

    const message = this.state.error.message || String(this.state.error);
    const stack = this.state.error.stack || '';

    return (
      <View style={styles.root}>
        <Text style={styles.title}>ModelMate не запустился</Text>
        <Text style={styles.subtitle}>Ошибка JavaScript при старте. Сделайте скриншот и отправьте в поддержку.</Text>
        <ScrollView style={styles.box} contentContainerStyle={styles.boxContent}>
          <Text style={styles.mono}>{message}</Text>
          {stack ? <Text style={styles.stack}>{stack}</Text> : null}
        </ScrollView>
        <Pressable style={styles.btn} onPress={this.retry}>
          <Text style={styles.btnText}>Повторить</Text>
        </Pressable>
      </View>
    );
  }
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: color.bg,
    paddingHorizontal: 20,
    paddingTop: 56,
    paddingBottom: 32,
    gap: 12,
  },
  title: {
    fontFamily: font.displayBold,
    fontSize: 20,
    color: color.text,
  },
  subtitle: {
    fontFamily: font.body,
    fontSize: 14,
    lineHeight: 20,
    color: color.muted,
  },
  box: {
    flex: 1,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: color.border,
    backgroundColor: color.card,
  },
  boxContent: {
    padding: 14,
    gap: 10,
  },
  mono: {
    fontFamily: font.mono,
    fontSize: 12,
    lineHeight: 18,
    color: color.lime,
  },
  stack: {
    fontFamily: font.mono,
    fontSize: 10,
    lineHeight: 15,
    color: color.dim,
  },
  btn: {
    alignSelf: 'center',
    backgroundColor: color.lime,
    borderRadius: 12,
    paddingHorizontal: 22,
    paddingVertical: 12,
  },
  btnText: {
    fontFamily: font.bodyBold,
    fontSize: 14,
    color: color.limeText,
  },
});
