/**
 * Test utilities for composable specs.
 *
 * Vue composables that call `onMounted` / `onUnmounted` /
 * `onBeforeRouteLeave` need an active component instance — calling
 * them directly in a test triggers the "no active component
 * instance to be associated with" warning on every test.
 *
 * `withSetup` runs the composable inside a minimal component's
 * setup() so the lifecycle hooks have a valid scope, then returns
 * the composable's return value via closure-capture (so refs stay
 * intact; `wrapper.vm` would auto-unwrap them and break
 * `result.someRef.value` patterns the tests use).
 */
import { shallowMount } from '@vue/test-utils'
import { defineComponent } from 'vue'

export const withSetup = <T>(setupFn: () => T): T => {
  let captured: T | undefined
  const TestComp = defineComponent({
    setup() {
      captured = setupFn()
      return () => null
    },
  })
  shallowMount(TestComp)
  return captured as T
}
